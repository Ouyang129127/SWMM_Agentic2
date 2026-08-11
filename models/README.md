# SWMM-2D Models Directory

本目录是所有 SWMM-2D 模型项目的统一入口。每一个一级子目录代表一个独立模型项目，彼此地位平行。

## Recommended Layout

```text
models/
  songhua_swmm_2d/
    model.yaml
    raw/
    static/
    swmm/
    mapping/
    events/
    runs/
  hebei_swmm_2d/
    model.yaml
    raw/
    static/
    swmm/
    mapping/
    events/
    runs/
  hunan_swmm_2d/
    ...
```

## Project Naming Rule

项目名就是 `models/` 下的一级目录名。

例如：

- `models/songhua_swmm_2d` 的项目名是 `songhua_swmm_2d`
- `models/hebei_swmm_2d` 的项目名是 `hebei_swmm_2d`
- `models/hunan_swmm_2d` 的项目名是 `hunan_swmm_2d`

工具和 Agent 应优先根据用户明确给出的项目名定位项目。如果用户没有指定项目名：

- 当 `models/` 下只有一个项目时，可以自动选择该项目。
- 当 `models/` 下有多个项目时，应先列出可用项目，并要求用户选择一个项目，不能默认使用某个固定项目。

## Required Project Structure

每个模型项目建议保持以下最小结构：

```text
models/<model_name>/
  model.yaml
  raw/
  static/
    config.json
    elevation.npy
    smid_grid.npy
    flow_mask.npy
    building_mask.npy
    resistance.npy
    node_to_cell_mapping.csv
  swmm/
    scenarios/
      baseline/
        model.inp
  mapping/
  events/
  runs/
```

## Directory Meanings

- `model.yaml`: 项目元数据，用于记录模型名称、区域、坐标系、数据来源、版本等信息。
- `raw/`: 原始资料和未加工数据。
- `static/`: 可复用的 CA2D 静态地表模型，包括地形、网格、阻力、建筑掩膜、流动掩膜和节点映射。
- `swmm/`: SWMM 模型文件和工程情景。
- `swmm/scenarios/baseline/model.inp`: 默认基线 SWMM 输入文件。
- `mapping/`: SWMM 节点、管网、地表网格、区域等映射辅助文件。
- `events/`: 降雨事件文件，例如 `rain1.txt`。
- `runs/`: 每次模拟运行的输出目录，建议按 `run_id` 分子目录保存结果。

## Query And Validation Rules

项目完整性检查应检查项目根目录：

```text
models/<model_name>/
```

CA2D 静态模型完整性检查应检查：

```text
models/<model_name>/static/
```

完整 SWMM-2D 降雨模拟应优先使用：

```text
models/<model_name>/swmm/scenarios/<scenario_name>/model.inp
models/<model_name>/events/<rainfall_file>
models/<model_name>/static/
models/<model_name>/runs/<run_id>/
```

不要将某一个项目名写死到工具或提示词中，例如不要默认写死 `songhua_swmm_2d`。后续新增 `hebei_swmm_2d`、`hunan_swmm_2d` 等平行项目时，应通过 `models/` 目录发现项目，并按项目名选择。

## Important Consistency Rule

为了让工具稳定查询和自动执行，各项目应尽量保持同一套目录命名。避免不同项目使用不同名称表达同一含义，例如：

- 不要有的项目叫 `static/`，有的项目叫 `ca2d/` 或 `static_model/`。
- 不要有的项目把基线文件放在 `swmm/scenarios/baseline/model.inp`，有的项目放在项目根目录。
- 不要有的项目把降雨事件放在 `events/`，有的项目放在 `rainfall/`。

统一结构比目录名本身更重要。只要所有项目都遵守同一套约定，Agent 和工具就可以可靠地发现、检查和运行多个平行模型项目。
