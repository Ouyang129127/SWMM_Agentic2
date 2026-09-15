"""Register the user-provided map screenshots to the SWMM coordinate system.

The screenshots contain the same grey subcatchment markers as the 218 SWMM
subcatchment polygons.  Marker centroids are detected and matched to polygon
centroids, then a robust affine transform is fitted.  The resulting transform
is stored as JSON so the CA2D builder itself only needs NumPy and Pillow.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


PROJECT = Path(__file__).resolve().parents[1]
INP = PROJECT / "swmm" / "scenarios" / "baseline" / "model.inp"
REFERENCES = PROJECT / "raw" / "references"


def parse_polygons(path: Path) -> dict[str, list[tuple[float, float]]]:
    polygons: dict[str, list[tuple[float, float]]] = {}
    current = None
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].upper()
            continue
        if current == "POLYGONS":
            row = line.split()
            if len(row) >= 3:
                polygons.setdefault(row[0], []).append((float(row[1]), float(row[2])))
    return polygons


def polygon_centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    xy = np.asarray(points, dtype=float)
    x = xy[:, 0]
    y = xy[:, 1]
    x2 = np.roll(x, -1)
    y2 = np.roll(y, -1)
    cross = x * y2 - x2 * y
    area2 = cross.sum()
    if abs(area2) < 1e-9:
        return float(x.mean()), float(y.mean())
    return (
        float(((x + x2) * cross).sum() / (3.0 * area2)),
        float(((y + y2) * cross).sum() / (3.0 * area2)),
    )


def grey_marker_centres(image: np.ndarray) -> np.ndarray:
    # The map's subcatchment marker fill is exact RGB 128/128/128. Orange
    # markup can obscure some markers, hence the deliberately tight size gate.
    mask = np.all(image[:, :, :3] == 128, axis=2).astype(np.uint8)
    count, labels, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    keep = []
    for idx in range(1, count):
        x, y, w, h, area = stats[idx]
        if 45 <= area <= 90 and 7 <= w <= 11 and 7 <= h <= 11:
            keep.append(centres[idx])
    return np.asarray(keep, dtype=float)


def initial_match(world: np.ndarray, pixels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    wn = (world - world.min(axis=0)) / np.maximum(world.ptp(axis=0), 1e-12)
    wn[:, 1] = 1.0 - wn[:, 1]
    pn = (pixels - pixels.min(axis=0)) / np.maximum(pixels.ptp(axis=0), 1e-12)
    cost = np.linalg.norm(wn[:, None, :] - pn[None, :, :], axis=2)
    wi, pi = linear_sum_assignment(cost)
    return wi, pi


def apply_affine(points: np.ndarray, affine: np.ndarray) -> np.ndarray:
    return np.column_stack([points, np.ones(len(points))]) @ affine.T


def fit_registration(world: np.ndarray, pixels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    wi, pi = initial_match(world, pixels)
    affine, _ = cv2.estimateAffine2D(world[wi], pixels[pi], method=cv2.RANSAC, ransacReprojThreshold=12.0)
    if affine is None:
        raise RuntimeError("Unable to initialise screenshot registration")
    for threshold in (12.0, 8.0, 6.0, 5.0):
        predicted = apply_affine(world, affine)
        cost = np.linalg.norm(predicted[:, None, :] - pixels[None, :, :], axis=2)
        wi, pi = linear_sum_assignment(cost)
        candidate, inlier = cv2.estimateAffine2D(
            world[wi], pixels[pi], method=cv2.RANSAC,
            ransacReprojThreshold=threshold, maxIters=10000, confidence=0.999,
        )
        if candidate is not None:
            affine = candidate
    predicted = apply_affine(world[wi], affine)
    residual = np.linalg.norm(predicted - pixels[pi], axis=1)
    return affine, residual, np.column_stack([wi, pi])


def register(name: str, image_path: Path, world: np.ndarray) -> dict:
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(image_path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    markers = grey_marker_centres(rgb)
    affine, residual, pairs = fit_registration(world, markers)
    accepted = residual <= 10.0
    result = {
        "name": name,
        "image": str(image_path.relative_to(PROJECT)),
        "image_width_px": int(rgb.shape[1]),
        "image_height_px": int(rgb.shape[0]),
        "detected_markers": int(len(markers)),
        "swmm_polygon_centroids": int(len(world)),
        "world_to_pixel_affine": affine.tolist(),
        "matched_pairs": int(len(residual)),
        "matches_within_10px": int(accepted.sum()),
        "residual_median_px": float(np.median(residual)),
        "residual_95p_px": float(np.quantile(residual, 0.95)),
        "residual_max_px": float(np.max(residual)),
    }

    overlay = rgb.copy()
    predicted = apply_affine(world, affine)
    for px, py in predicted:
        cv2.circle(overlay, (round(px), round(py)), 3, (0, 200, 0), 1)
    for (wi, pi), err in zip(pairs, residual):
        if err <= 10.0:
            p1 = tuple(np.rint(predicted[wi]).astype(int))
            p2 = tuple(np.rint(markers[pi]).astype(int))
            cv2.line(overlay, p1, p2, (0, 180, 0), 1)
    cv2.imwrite(str(REFERENCES / f"{name}_registration_overlay.png"), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    return result


def register_roads_from_domain(domain_path: Path, road_path: Path, world_to_domain: np.ndarray, world: np.ndarray) -> dict:
    """Use shared cartographic features to transfer the domain registration.

    This is more reliable than point-set matching for the road screenshot,
    because orange road strokes obscure a subset of its grey markers.
    """
    domain = cv2.imread(str(domain_path), cv2.IMREAD_COLOR)
    roads = cv2.imread(str(road_path), cv2.IMREAD_COLOR)
    if domain is None or roads is None:
        raise FileNotFoundError("Reference screenshot missing")

    def without_orange(image: np.ndarray) -> np.ndarray:
        clean = image.copy()
        b, g, r = cv2.split(clean)
        orange = (r > 210) & (g > 25) & (g < 180) & (b < 100)
        clean[orange] = 255
        return cv2.cvtColor(clean, cv2.COLOR_BGR2GRAY)

    g1 = without_orange(domain)
    g2 = without_orange(roads)
    sift = cv2.SIFT_create(nfeatures=12000, contrastThreshold=0.015)
    k1, d1 = sift.detectAndCompute(g1, None)
    k2, d2 = sift.detectAndCompute(g2, None)
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(d1, d2, k=2)
    good = [a for a, b in pairs if a.distance < 0.72 * b.distance]
    src = np.float32([k1[m.queryIdx].pt for m in good])
    dst = np.float32([k2[m.trainIdx].pt for m in good])
    domain_to_road, inlier = cv2.estimateAffine2D(
        src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0,
        maxIters=20000, confidence=0.999, refineIters=50,
    )
    if domain_to_road is None:
        raise RuntimeError("Unable to register road screenshot from shared map features")
    w2d = np.vstack([world_to_domain, [0.0, 0.0, 1.0]])
    d2r = np.vstack([domain_to_road, [0.0, 0.0, 1.0]])
    world_to_road = (d2r @ w2d)[:2]

    road_rgb = cv2.cvtColor(roads, cv2.COLOR_BGR2RGB)
    markers = grey_marker_centres(road_rgb)
    predicted = apply_affine(world, world_to_road)
    cost = np.linalg.norm(predicted[:, None, :] - markers[None, :, :], axis=2)
    wi, pi = linear_sum_assignment(cost)
    residual = cost[wi, pi]

    overlay = road_rgb.copy()
    for px, py in predicted:
        cv2.circle(overlay, (round(px), round(py)), 4, (0, 200, 0), 1)
    cv2.imwrite(str(REFERENCES / "roads_registration_overlay.png"), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    return {
        "name": "roads",
        "image": str(road_path.relative_to(PROJECT)),
        "image_width_px": int(roads.shape[1]),
        "image_height_px": int(roads.shape[0]),
        "detected_markers": int(len(markers)),
        "swmm_polygon_centroids": int(len(world)),
        "domain_to_road_affine": domain_to_road.tolist(),
        "world_to_pixel_affine": world_to_road.tolist(),
        "sift_matches": int(len(good)),
        "sift_inliers": int(inlier.sum()),
        "matched_pairs": int(len(residual)),
        "matches_within_10px": int((residual <= 10.0).sum()),
        "residual_median_px": float(np.median(residual)),
        "residual_95p_px": float(np.quantile(residual, 0.95)),
        "residual_max_px": float(np.max(residual)),
    }


def main() -> None:
    polygons = parse_polygons(INP)
    world = np.asarray([polygon_centroid(points) for points in polygons.values()])
    domain_path = REFERENCES / "model_domain_reference.png"
    road_path = REFERENCES / "road_distribution_reference.png"
    domain_result = register("domain", domain_path, world)
    results = {
        "method": "robust affine fit between SWMM polygon centroids and screenshot grey markers",
        "domain": domain_result,
        "roads": register_roads_from_domain(
            domain_path, road_path,
            np.asarray(domain_result["world_to_pixel_affine"], dtype=float), world,
        ),
    }
    output = REFERENCES / "reference_registration.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
