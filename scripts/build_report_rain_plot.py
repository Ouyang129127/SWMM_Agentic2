"""Preview the rainfall figure from a report's verified rainfall input."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from workflow_agents.reporting.materials import assert_sources_current, rainfall_metrics
from workflow_agents.reporting.plots import make_rainfall_plot
from workflow_agents.reporting.pipeline import producer_hashes


def run(args):
    source=Path(args.materials).resolve()
    materials=json.loads(source.read_text(encoding='utf-8'))
    assert_sources_current(materials)
    copies=[Path(path) for path in materials['source_hashes'] if Path(path).name=='rainfall_event.txt']
    if len(copies)!=1:
        raise ValueError('Expected one verified rainfall input copy')
    _metrics,frame,cumulative=rainfall_metrics(copies[0],materials['scene']['rain_end'])
    output=Path(args.output_dir).resolve()
    output.mkdir(parents=True,exist_ok=False)
    media=make_rainfall_plot(materials,frame,cumulative,output)
    assert_sources_current(materials)
    audit={'status':'completed','source':'program_plot','source_materials':str(source),
           'source_hashes':materials['source_hashes'],'producer_hashes':producer_hashes(),'media':media}
    (output/'plot_result.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(media,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--materials',required=True)
    parser.add_argument('--output-dir',required=True)
    run(parser.parse_args())
