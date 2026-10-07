"""Build fixed rainfall prose from the verified run copy, preserving other sections."""
import argparse

from build_report_scene import run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', required=True)
    parser.add_argument('--narrative-source', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    args.section = 'rain'
    run(args)
