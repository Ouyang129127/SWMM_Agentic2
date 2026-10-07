"""Report behavior across arbitrary events, invalid writing and failed delivery."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
from PIL import Image

from workflow_agents.reporting.materials import SECTIONS, assert_sources_current, rainfall_metrics, saved_time_metrics
from workflow_agents.reporting.narrative import make_prompt, validate, write_narrative
from workflow_agents.reporting.pipeline import attach_display_report, check_html, generate_display_report
from workflow_agents.reporting.plots import make_plots
from workflow_agents.reporting.render import render
from workflow_agents.reference_checks import sha256_file


def example(nodes=('Junction_A','Junction_A','Outlet_B')):
    threshold={'max_area_m2':0.,'max_area_time':None,'final_area_m2':0.,
        'categories':{k:{'peak_area_m2':0.,'peak_time':None,'final_area_m2':0.} for k in ('road','green','building_adjacent')}}
    event=lambda n,i:{'node_id':n,'event_id':f'{n}:E{i:03}', 'start':'2024-01-01 00:05:00',
        'end':'2024-01-01 00:10:00','duration_minutes':5.,'estimated_volume_m3':2.,'peak_flooding_Ls':5.,'occurrence':i}
    events=[]
    for i,n in enumerate(nodes,1):
        e=event(n,i)
        events.append({'event':e,'event_id':e['event_id'],'node_id':n,'process':[
            {'time':t,'total_inflow_Ls':10.,'outflow_Ls':5.,'flooding_Ls':5.,'depth_m':1.}
            for t in ('2024-01-01 00:05:00','2024-01-01 00:10:00')],
            'source_composition':{'sources':[]},'incident_links':{},'surface_associations':[],
            'storage_evidence':None,'allow_simple_peak_balance':True,
            'assessment':{'process_explanation':'已有过程。','joint_assessment':{},'alternatives':'',
                'mechanism_assessments':[{'mechanism_id':'M1','status':'supported','reason':'来水集中。'},
                                        {'mechanism_id':'M3','status':'candidate','reason':'下游可能影响。'}]}})
    return {'revision':1,'task_id':'test','model_name':'test_model','run_id':'test_run','scope':'global',
        'scene':{'model_display_name':'示例模型','scenario_display_name':'示例方案',
        'simulation_start':'2024-01-01 00:00:00','simulation_end':'2024-01-01 00:15:00',
        'rain_end':'2024-01-01 00:10:00','run_date':'2026-10-07'},
        'rain':{'total_mm':10.,'peak_mm_h':60.,'shape':'单峰降雨'},
        'surface':{'classification_available':True,'max_saved_depth_m':.05,'max_depth_time':'2024-01-01 00:05:00',
                   'threshold_metrics':{'0.01':copy.deepcopy(threshold),'0.15':copy.deepcopy(threshold)},'process':[]},
        'overflow':{'node_count':len(set(nodes)),'event_count':len(nodes),'total_volume_m3':2.*len(nodes)},
        'events':events,'task_context':{},'diagnosis_overview':{},'verified_claims':[],
        'numeric_notes':[],'source_hashes':{}}


def answer(prompt):
    result={'intro':'依据本次保存结果说明降雨、地表变化与管网成因。',
        'sections':{k:['本次模拟结果按实际过程分析。'] for k in SECTIONS},
        'events':[{'event_id':eid,'process':['来水期间发生冒溢。'],
            'supported_mechanism_ids':['M1'],'supported_causes':['来水集中形成排水压力。'],
            'candidate_mechanism_ids':['M3'],'candidate_influences':['下游水位可能影响排水。']}
            for eid in prompt['expected_event_ids']]}
    for key,tokens in prompt.get('required_facts_by_section',{}).items():
        result['sections'][key].append('；'.join(tokens)+'。')
    for event,source in zip(result['events'],prompt['materials']['events']):
        event['process']=['；'.join(token for token in source['event'].values() if token)+'。']
    return result


class ReportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.materials=example();self.prompt,self.facts=make_prompt(self.materials)

    def tearDown(self):self.tmp.cleanup()

    def valid(self,response):return validate(response,self.materials,self.facts,['Junction_A','Outlet_B'])

    def test_all_events_including_repeated_node_are_required(self):
        r=answer(self.prompt);self.valid(r);r['events'].pop()
        with self.assertRaisesRegex(ValueError,'every event'):self.valid(r)

    def test_duplicate_event_is_rejected(self):
        r=answer(self.prompt);r['events'][1]=copy.deepcopy(r['events'][0])
        with self.assertRaisesRegex(ValueError,'every event'):self.valid(r)

    def test_supported_and_candidate_cannot_be_upgraded(self):
        r=answer(self.prompt);r['events'][0]['supported_mechanism_ids'].append('M3')
        with self.assertRaisesRegex(ValueError,'status/coverage'):self.valid(r)

    def test_candidate_must_retain_uncertainty(self):
        r=answer(self.prompt);r['events'][0]['candidate_influences']=['下游顶托是主要原因。']
        with self.assertRaisesRegex(ValueError,'explicitly possible'):self.valid(r)

    def test_unconfirmed_candidate_cannot_be_rewritten_as_a_small_effect(self):
        r=answer(self.prompt);r['events'][0]['candidate_influences']=['下游可能形成顶托，顶托作用可能有限。']
        with self.assertRaisesRegex(ValueError,'limited-effect'):self.valid(r)

    def test_full_pipe_cannot_be_rewritten_as_permanently_constant_flow(self):
        r=answer(self.prompt);r['events'][0]['supported_causes']=['满流后出流无法继续增加，节点水位升高。']
        with self.assertRaisesRegex(ValueError,'constant outflow'):self.valid(r)

    def test_unconnected_nodes_cannot_be_presented_as_a_pipe_chain(self):
        r=answer(self.prompt);r['sections']['causes']=['Junction_A—Outlet_B构成连续管网链。']
        with self.assertRaisesRegex(ValueError,'branching topology'):self.valid(r)

    def test_fabricated_numeric_claim_and_unknown_token_rejected(self):
        for sentence in ('持续了99分钟。','面积为[[F9999]]。'):
            r=answer(self.prompt);r['intro']=sentence
            with self.assertRaises(ValueError):self.valid(r)

    def test_known_fact_references_expand_without_exposing_tokens(self):
        r=answer(self.prompt);r['intro']=self.prompt['materials']['rain']['total_mm']+'。'
        self.valid(r)
        media=self.images();p=self.root/'report.html'
        render(self.materials,r,self.facts,media,p,'now');checks=check_html(p,self.materials)
        self.assertEqual(checks['events'],3);self.assertNotIn('[[F',p.read_text(encoding='utf-8'))
        self.assertIn('10.0毫米',p.read_text(encoding='utf-8'))

    def images(self):
        p=self.root/'image.png';Image.new('RGB',(12,12),'white').save(p)
        return {k:{'path':str(p),'caption':'实际图像'} for k in ('rainfall','surface_maps','surface_process','surface_stages')}

    def test_zero_overflow_still_renders_six_sections(self):
        m=example(());prompt,facts=make_prompt(m);r=answer(prompt)
        validate(r,m,facts,[]);p=self.root/'zero.html'
        render(m,r,facts,self.images(),p,'now')
        self.assertEqual(check_html(p,m)['events'],0)

    def test_complete_fact_cannot_be_embedded_as_a_scalar(self):
        r=answer(self.prompt);r['intro']='总雨量为'+self.prompt['materials']['rain']['total_mm']+'。'
        with self.assertRaisesRegex(ValueError,'standalone clause'):self.valid(r)

    def test_local_rise_and_plateau_are_available_without_all_metric_sentences(self):
        m=example(('Junction_A',))
        m['events'][0]['process'].insert(1,{'time':'2024-01-01 00:07:00',
            'total_inflow_Ls':12.,'outflow_Ls':5.,'flooding_Ls':7.,'depth_m':1.})
        prompt,facts=make_prompt(m)
        rows=prompt['materials']['events'][0]['process']
        self.assertEqual(len(rows),3)
        comparison=facts[rows[1]['flow_comparison'][2:-2]]
        self.assertIn('00:07',comparison);self.assertIn('12.0升/秒',comparison)
        self.assertNotIn('节点水深',comparison);self.assertNotIn('冒溢流量',comparison)
        self.assertIn('节点水深',facts[rows[1]['depth'][2:-2]])

    def test_current_event_cannot_use_another_event_numeric_fact(self):
        r=answer(self.prompt)
        r['events'][0]['process'].append(self.prompt['materials']['events'][1]['event']['summary']+'。')
        with self.assertRaisesRegex(ValueError,'another event'):self.valid(r)

    def test_teaching_fact_tokens_cannot_escape_into_current_report(self):
        r=answer(self.prompt);r['events'][0]['process'].append('[[EX001]]。')
        with self.assertRaisesRegex(ValueError,'Teaching example fact'):self.valid(r)

    def test_internal_assessment_patch_is_rejected_but_natural_possible_language_passes(self):
        r=answer(self.prompt);r['events'][0]['candidate_influences']=['下游水位可能影响排水，但尚未证实。']
        with self.assertRaisesRegex(ValueError,'reader-facing'):self.valid(r)
        r['events'][0]['candidate_influences']=['下游高水位可能限制向下游排水。']
        self.valid(r)

    def test_node_title_is_rendered_and_checked_for_unbound_numbers(self):
        r=answer(self.prompt);r['events'][0]['title']='Junction_A：来水集中，排水压力增加'
        self.valid(r)
        p=self.root/'titled.html';render(self.materials,r,self.facts,self.images(),p,'now')
        self.assertIn('Junction_A：来水集中，排水压力增加',p.read_text(encoding='utf-8'))
        r['events'][0]['title']='Junction_A：持续99分钟'
        with self.assertRaisesRegex(ValueError,'Unbound numeric'):self.valid(r)

    def test_numeric_flow_mismatch_does_not_block_head_description(self):
        self.materials['events'][0]['allow_simple_peak_balance']=False
        r=answer(self.prompt);r['events'][0]['supported_causes']=['水头等于井口高程时发生冒溢。']
        self.valid(r)
        r['events'][0]['process'].append('入流与出流差值等于冒溢流量。')
        with self.assertRaisesRegex(ValueError,'flow equality'):self.valid(r)

    def test_process_metric_dump_is_rejected_but_selected_comparison_passes(self):
        r=answer(self.prompt)
        snapshot=self.prompt['materials']['events'][0]['process'][0]
        r['events'][0]['process'].append('；'.join(snapshot[k] for k in ('flow_comparison','depth','flooding'))+'。')
        with self.assertRaisesRegex(ValueError,'too many sampled metrics'):self.valid(r)
        r['events'][0]['process'][-1]=snapshot['flow_comparison']+'。来水增加了节点的排水压力。'
        self.valid(r)

    def test_peak_comparison_cannot_move_the_overflow_onset(self):
        m=example(('Junction_A',));m['events'][0]['event']['peak_time']='2024-01-01 00:07:00'
        m['events'][0]['process'][0]['time']='2024-01-01 00:04:00'
        row=copy.deepcopy(m['events'][0]['process'][0]);row['time']='2024-01-01 00:07:00'
        m['events'][0]['process'].insert(1,row)
        prompt,facts=make_prompt(m);r=answer(prompt)
        peak=prompt['materials']['events'][0]['process'][1]['flow_comparison']
        r['events'][0]['process'].append(peak+'。节点水位升高并开始冒溢。')
        with self.assertRaisesRegex(ValueError,'after onset'):validate(r,m,facts,['Junction_A'])
        r['events'][0]['process'][-1]=peak+'。节点处于冒溢高峰。'
        validate(r,m,facts,['Junction_A'])

    def test_simultaneous_onsets_cannot_be_described_as_sequential(self):
        r=answer(self.prompt);r['events'][2]['process'].append('Outlet_B紧随Junction_A之后发生冒溢。')
        with self.assertRaisesRegex(ValueError,'same saved time'):self.valid(r)

    def test_downstream_context_distinguishes_earlier_overflow_from_concurrent_water_level(self):
        m=example(('Up','Down'))
        m['events'][0]['event'].update(start='2024-01-01 00:10:00',end='2024-01-01 00:15:00')
        m['events'][0]['incident_links']={'Pipe':{'from_node':'Up','to_node':'Down'}}
        prompt,facts=make_prompt(m);r=answer(prompt)
        self.assertIn('已在本事件开始前结束',prompt['materials']['events'][0]['downstream_event_context'][0]['relation'])
        r['events'][0]['candidate_influences']=['下游Down尚未冒溢，其高水位可能影响排水。']
        with self.assertRaisesRegex(ValueError,'already ended'):validate(r,m,facts,['Up','Down','Pipe'])
        r['events'][0]['candidate_influences']=['下游Down的同期高水位可能限制向下游排水。']
        validate(r,m,facts,['Up','Down','Pipe'])

    def test_html_and_internal_labels_are_rejected(self):
        for text in ('<script>危险</script>','M1导致冒溢。'):
            r=answer(self.prompt);r['intro']=text
            with self.assertRaises(ValueError):self.valid(r)

    async def test_bad_model_response_receives_one_repair(self):
        invalid=answer(self.prompt);invalid['events']=[]
        callback=AsyncMock(side_effect=[invalid,answer(self.prompt)])
        r,_=await write_narrative(self.materials,['Junction_A','Outlet_B'],self.root,callback)
        self.assertEqual(len(r['events']),3);self.assertEqual(callback.await_count,2)
        self.assertIn('repair',callback.call_args.args[0])

    async def test_network_failure_is_preserved_without_fallback_prose(self):
        callback=AsyncMock(side_effect=RuntimeError('service unavailable'))
        with self.assertRaisesRegex(RuntimeError,'service unavailable'):
            await write_narrative(self.materials,[],self.root,callback)
        self.assertEqual(callback.await_count,1)
        self.assertEqual(json.loads((self.root/'narrative_attempt_1.json').read_text())['status'],'failed')

    def test_irregular_rain_intervals_and_rolling_30_minutes(self):
        p=self.root/'rain.csv'
        pd.DataFrame({'timestamp':['2024-01-01 00:00:00','2024-01-01 00:10:00','2024-01-01 00:30:00','2024-01-01 00:50:00'],
                      'value':[0.,60.,30.,0.]}).to_csv(p,index=False)
        metrics,_,_=rainfall_metrics(p,'2024-01-01 00:50:00')
        self.assertAlmostEqual(metrics['total_mm'],30.);self.assertAlmostEqual(metrics['window_mm'],25.)
        self.assertEqual(metrics['window_start'],'2024-01-01 00:10:00')

    def test_short_and_zero_rain(self):
        p=self.root/'rain.csv'
        for rate,total in ((60.,20.),(0.,0.)):
            pd.DataFrame({'timestamp':['2024-01-01 00:00:00','2024-01-01 00:20:00'],'value':[rate,0.]}).to_csv(p,index=False)
            metrics,_,_=rainfall_metrics(p,'2024-01-01 00:20:00')
            self.assertEqual(metrics['window_minutes'],20.);self.assertEqual(metrics['window_mm'],total)

    def test_source_mutation_is_rejected(self):
        p=self.root/'source.json';p.write_text('original')
        materials={'source_hashes':{str(p):sha256_file(p)}};assert_sources_current(materials)
        p.write_text('changed')
        with self.assertRaisesRegex(ValueError,'source changed'):assert_sources_current(materials)

    def test_last_rain_interval_is_included_without_terminal_zero(self):
        p=self.root/'rain.csv'
        pd.DataFrame({'timestamp':['2024-01-01 00:00:00'],'value':[60.]}).to_csv(p,index=False)
        metrics,frame,cumulative=rainfall_metrics(p,'2024-01-01 00:20:00')
        self.assertEqual(metrics['total_mm'],20.);self.assertEqual(len(frame),2)
        self.assertEqual(cumulative[-1],20.)

    def test_surface_facts_bind_time_and_area_in_one_reference(self):
        m=example(())
        m['surface']['threshold_metrics']['0.01'].update(rain_end_area_m2=828.,
            rain_end_sample_time='2024-01-01 00:10:00',final_area_m2=819.)
        prompt,facts=make_prompt(m)
        from workflow_agents.reporting.narrative import expand
        rain_end=expand(prompt['materials']['surface']['general']['rain_end'],facts)
        final=expand(prompt['materials']['surface']['general']['final'],facts)
        self.assertIn('00:10',rain_end);self.assertIn('828',rain_end);self.assertNotIn('819',rain_end)
        self.assertIn('00:15',final);self.assertIn('819',final)

    def test_microsecond_and_nanosecond_indices_select_same_rain_end(self):
        times=pd.date_range('2024-01-01',periods=85,freq='5min')
        for unit in ('us','ns'):
            steps,nearest=saved_time_metrics(times.as_unit(unit),'2024-01-01 04:00:00')
            self.assertEqual(nearest,48);self.assertEqual(steps[0],5.)
            self.assertEqual(steps.sum(),420.)

    def test_lateral_source_uses_display_name_instead_of_internal_field(self):
        m=example();m['events'][0]['source_composition']['sources']=[{'source_id':'aggregate_lateral','event_volume_share':1.}]
        prompt,facts=make_prompt(m)
        source=prompt['materials']['events'][0]['source_composition']['sources'][0]
        self.assertEqual(source['source_name'],'侧向入流')
        self.assertFalse(any('aggregate_lateral' in text for text in facts.values()))

    def test_rain_peak_relation_is_required_in_overflow_prose(self):
        m=example();m['overflow'].update(first_start='2024-01-01 00:05:00',last_end='2024-01-01 00:10:00')
        m['rain'].update(peak_start='2024-01-01 00:00:00',peak_end='2024-01-01 00:10:00',peak_interval_min=10.)
        prompt,facts=make_prompt(m);r=answer(prompt);validate(r,m,facts,['Junction_A','Outlet_B'])
        token=prompt['materials']['overflow']['rain_peak_relation'];self.assertIn('区间内',facts[token[2:-2]])
        r['sections']['overflow']=['峰值附近发生冒溢。']
        with self.assertRaisesRegex(ValueError,'rain-peak relation'):validate(r,m,facts,['Junction_A','Outlet_B'])

    def test_attention_location_and_duration_cannot_be_omitted(self):
        m=example();m['events'][0]['surface_associations']=[{'land_type':'道路','max_saved_depth_m':.16,
            'max_depth_time':'2024-01-01 00:05:00','final_depth_m':0.,'meaning':'注入网格',
            'attention_episodes':[{'first_saved':'2024-01-01 00:05:00','last_saved':'2024-01-01 00:05:00',
                'continuous_episode_upper_estimate_min':10.,'boundary_censored':False}]}]
        prompt,facts=make_prompt(m);r=answer(prompt);validate(r,m,facts,['Junction_A','Outlet_B'])
        token=prompt['required_facts_by_section']['surface'][0]
        self.assertIn('不超过10分钟',facts[token[2:-2]]);self.assertIn('道路',facts[token[2:-2]])
        r['sections']['surface']=['短时积水随后消退。']
        with self.assertRaisesRegex(ValueError,'location/duration'):validate(r,m,facts,['Junction_A','Outlet_B'])

    async def test_full_pipeline_and_unchanged_reuse(self):
        state={'task_id':'test','revision':1,'diagnosis_hash':'hash'}
        (self.root/'task.json').write_text(json.dumps(state))
        with patch('workflow_agents.reporting.pipeline.prepare_materials',return_value=(self.materials,{'known_ids':['Junction_A','Outlet_B']})), \
             patch('workflow_agents.reporting.pipeline.make_plots',return_value=(self.images(),[])), \
             patch('workflow_agents.reporting.pipeline.verify_task'):
            callback=AsyncMock(side_effect=answer)
            result=await attach_display_report(self.root,self.root,state,callback)
            self.assertEqual(result['status'],'completed');self.assertTrue(Path(result['html_file']).is_file())
            repeat=await attach_display_report(self.root,self.root,state,callback)
            self.assertTrue(repeat['reused']);self.assertEqual(callback.await_count,1)

    async def test_new_revision_failure_does_not_present_previous_html_as_current(self):
        old={'status':'completed','revision':1,'html_file':'old.html'}
        state={'task_id':'test','revision':2,'display_report':old,'display_report_file':'old.html','display_report_revision':1}
        callback=AsyncMock()
        with patch('workflow_agents.reporting.pipeline.prepare_materials',side_effect=ValueError('stale evidence')):
            result=await attach_display_report(self.root,self.root,state,callback)
        self.assertEqual(result['status'],'failed');self.assertNotIn('display_report_file',state)
        self.assertEqual(state['previous_display_report'],old);callback.assert_not_called()

    def test_zero_events_maps_no_attention_and_no_road_classification(self):
        m=example(());m['surface']['classification_available']=False
        times=pd.date_range('2024-01-01',periods=4,freq='5min');grid=np.arange(1,7).reshape(2,3)
        depth=np.zeros((4,2,3));depth[1,0,0]=.05
        d={'grid':grid,'flow':np.ones((2,3),bool),'road':np.zeros((2,3),bool),'green':np.ones((2,3),bool),
           'building':np.zeros((2,3),bool),'valid':np.ones((2,3),bool),'classification_available':False,
           'depth':depth,'times':times,'areas':{.01:np.array([0,9,0,0]),.15:np.zeros(4)},'max_depth':depth.max(axis=(1,2)),
           'phase_indices':[0,1,3],'rain_frame':pd.DataFrame({'timestamp':times,'value':[60,60,0,0]}),
           'cumulative_rain':[0,5,10,10],'mapping':pd.DataFrame(columns=['node_id','cell_col','cell_row']),'gif':None}
        media,layout=make_plots(m,d,self.root/'plots')
        self.assertEqual(len(media),4);self.assertEqual(layout,[])
        for image in media.values():
            with Image.open(image['path']) as im:im.verify()

    async def test_public_report_resolves_active_task_and_preserves_question(self):
        import main
        with patch('workflow_agents.investigation_flow.load_active_task',return_value={'task_id':'bound','state':'preliminary_delivered'}), \
             patch('main._investigation_action',new_callable=AsyncMock,return_value='result') as dispatch:
            await main.ReportAgent('model','run',message='生成展示报告')
        dispatch.assert_awaited_once_with('model','run','display_report','bound')
