"""Cross-entrypoint evidence safety regressions from the project audit.

These are author-owned regression fixtures, not independent review or a teacher study.
"""
import importlib.util
from pathlib import Path

import pytest

from emfeeld import model_runs, observations, cli, capabilities, study
from emfeeld.model_revisions import ModelStore
from test_model_revisions import imported, execute, configs, write

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('audit_question_trial', ROOT/'verification/question_first_trial_v1.py')
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)


def _inventory(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('through_alias', [False, True])
def test_new_native_run_cannot_damage_an_existing_sealed_run(tmp_path, through_alias):
    store, ref = imported(tmp_path)
    _, sealed = execute(tmp_path, store, ref, mode='static', name='sealed')
    before = _inventory(sealed)
    parent = sealed
    if through_alias:
        parent = tmp_path/'alias'
        try:
            parent.symlink_to(sealed, target_is_directory=True)
        except OSError:
            pytest.skip('directory symlinks unavailable in this environment')
    inv, analysis, view = configs(ref, mode='static')
    paths = [write(tmp_path/(key+'.json'), value) for key, value in
             zip(('ref', 'inv', 'analysis', 'view'), (ref, inv, analysis, view))]
    dest = parent/'new-run'
    with pytest.raises(ValueError, match='saved evidence'):
        model_runs.execute(store.path, *paths, dest, run_id='nested')
    assert not dest.exists()
    assert _inventory(sealed) == before
    assert model_runs.inspect_run(sealed)[2]['status'] == 'complete'


@pytest.mark.parametrize('entrypoint', ['observation', 'scene', 'catalogue', 'study', 'freeze', 'assess', 'import'])
def test_other_public_writers_cannot_change_sealed_evidence(tmp_path, entrypoint):
    store, ref = imported(tmp_path)
    _, sealed = execute(tmp_path, store, ref, mode='static', name='sealed')
    before = _inventory(sealed)
    dest = sealed/('result.json' if entrypoint in ('observation', 'scene', 'catalogue') else 'new-output')
    if entrypoint == 'observation':
        assert observations.main([str(ROOT/'examples/nasa_ion_public_v0/packet.json'), '--output', str(dest)]) == 2
    elif entrypoint == 'scene':
        assert cli.main(['run', str(ROOT/'examples/line_plane_fields.json'), '--output', str(dest)]) == 2
    elif entrypoint == 'catalogue':
        assert capabilities.main(['--output', str(dest)]) == 2
    else:
        with pytest.raises(ValueError, match='saved evidence'):
            if entrypoint == 'study':
                study.run_study(ROOT/'examples/studies/electric.json', dest)
            elif entrypoint == 'freeze':
                trial.freeze(ROOT/'examples/question_first_v1/developer_question.json', dest)
            elif entrypoint == 'assess':
                trial.assess(ROOT/'examples/nasa_ion_public_v0', ROOT/'examples/nasa_ion_public_v0/packet.json', dest)
            else:
                ModelStore.import_legacy(tmp_path/'store.source.json', tmp_path/'store.import.json', dest)
    assert not dest.exists()
    assert _inventory(sealed) == before
    assert model_runs.inspect_run(sealed)[2]['status'] == 'complete'


@pytest.mark.parametrize('part', ['analysis', 'replay', 'bounds', 'camera'])
def test_out_of_range_numeric_settings_produce_rejected_record_not_crash(tmp_path, part):
    store, ref = imported(tmp_path)
    def change(inv, analysis, view):
        if part == 'analysis': analysis['checks']['rtol'] = 10**400
        elif part == 'replay': view['replay_seconds'] = 10**400
        elif part == 'bounds': view['bounds_m'][0] = -(10**400)
        else: view['camera'] = [[10**400, 0, 0], [0, 0, 0], [0, 1, 0]]
    result, output = execute(tmp_path, store, ref, change=change)
    assert result['status'] == 'rejected'
    assert result['execution_complete'] is False
    assert not (output/'native').exists()
    assert model_runs.inspect_run(output)[2]['status'] == 'rejected'


@pytest.mark.parametrize('delta', [0.0, -1.0])
def test_parallel_camera_view_up_is_rejected_before_rendering(tmp_path, delta):
    store, ref = imported(tmp_path)
    rev, _ = store.read(ref)
    inv, analysis, view = configs(ref, mode='static')
    view['camera'] = [[0, 0, 2], [0, 0, 0], [0, 0, 1 if delta == 0 else -1]]
    with pytest.raises(ValueError, match='camera'):
        model_runs.lower(rev, inv, analysis, view)


@pytest.mark.parametrize('entrypoint', ['apply', 'sweep', 'derived', 'comparison', 'ensemble', 'replay'])
def test_higher_level_writers_preflight_unrelated_evidence_before_input_or_store_mutation(tmp_path, entrypoint):
    from emfeeld import model_cli, sweeps, derived_observations, scenario_comparisons, scenario_ensembles
    store, ref = imported(tmp_path)
    _, source = execute(tmp_path, store, ref, mode='static', name='source')
    _, victim = execute(tmp_path, store, ref, mode='static', name='victim')
    before_victim, before_store = _inventory(victim), _inventory(store.path)
    missing, output = tmp_path/'does-not-exist.json', victim/'new-evidence'
    with pytest.raises(ValueError, match='saved evidence'):
        if entrypoint == 'apply':
            model_cli.apply_revision(missing, store_path=store.path, using=source, output=output)
        elif entrypoint == 'sweep':
            sweeps.run_sweep(missing, store_path=store.path, using=source, output=output)
        elif entrypoint == 'derived':
            derived_observations.derive(missing, using=source, output=output)
        elif entrypoint == 'comparison':
            scenario_comparisons.compare(missing, left=source, right=source, output=output)
        elif entrypoint == 'ensemble':
            scenario_ensembles.run_ensemble(missing, store_path=store.path, using=source, output=output)
        else:
            spec = importlib.util.spec_from_file_location('audit_replay', ROOT/'tools/replay_packets.py')
            replay = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(replay)
            replay.replay(missing, output)
    assert not output.exists()
    assert _inventory(victim) == before_victim
    assert _inventory(store.path) == before_store
    assert model_runs.inspect_run(victim)[2]['status'] == 'complete'


def test_present_run_cannot_export_into_an_unrelated_sealed_run(tmp_path, monkeypatch):
    from emfeeld import viewer
    from test_model_revisions import base_scene
    scene = base_scene()
    scene['particles'] = []
    store, ref = imported(tmp_path, scene=scene, mutate=lambda spec: spec.update(particle_ids=[]))
    _, source = execute(tmp_path, store, ref, mode='static', name='source')
    _, victim = execute(tmp_path, store, ref, mode='static', name='victim')
    before = _inventory(victim)
    monkeypatch.setattr(viewer, 'make_plotter', lambda *a, **kw: pytest.fail('rendered before destination check'))
    with pytest.raises(ValueError, match='saved evidence'):
        model_runs.present_run(source, screenshot_directory=victim/'screenshots')
    assert _inventory(victim) == before
    assert model_runs.inspect_run(victim)[2]['status'] == 'complete'


@pytest.mark.parametrize('markers', [
    ('integrity.json',),
    ('model.json', 'revisions/', 'proposals/'),
    ('question.json', 'receipt.json'),
    ('study.json', 'summary.json'),
    ('manifest.json', 'summary.json'),
    ('started.json', 'outcome.json'),
])
def test_all_recognizable_evidence_roots_block_descendant_writes(tmp_path, markers):
    from emfeeld.output_safety import protect_saved_evidence
    root = tmp_path/'old-evidence'
    root.mkdir()
    for marker in markers:
        if marker.endswith('/'):
            (root/marker).mkdir()
        else:
            (root/marker).write_text('{}', encoding='utf-8')
    before = _inventory(root)
    with pytest.raises(ValueError, match='saved evidence'):
        protect_saved_evidence(root/'new'/'report.json')
    assert _inventory(root) == before


def test_unsealed_workflows_and_existing_ordinary_reports_keep_their_output_policy(tmp_path):
    from emfeeld.output_safety import protect_saved_evidence
    root = tmp_path/'building'
    root.mkdir()
    (root/'started.json').write_text('{}', encoding='utf-8')
    # Composition may create children before the final parent inventory exists.
    protect_saved_evidence(root/'child', new_directory=True)
    ordinary_report = tmp_path/'ordinary.json'
    ordinary_report.write_text('{}', encoding='utf-8')
    protect_saved_evidence(ordinary_report)
    with pytest.raises(FileExistsError):
        protect_saved_evidence(ordinary_report, new_directory=True)


@pytest.mark.parametrize('payload', [[], None, 'not-a-proposal', True, 7])
def test_nonobject_revision_proposal_is_rejected_without_store_writes(tmp_path, payload):
    store, _ = imported(tmp_path)
    before = _inventory(store.path)
    proposal = write(tmp_path/'invalid-proposal.json', payload)
    with pytest.raises(ValueError, match='JSON object'):
        store.revise(proposal)
    assert _inventory(store.path) == before


@pytest.mark.parametrize('order', [[{}], [[]], [1]])
def test_nonstring_entity_order_yields_rejected_run_not_unexpected_exception(tmp_path, order):
    store, ref = imported(tmp_path)
    def change(inv, analysis, view):
        view['entity_order'] = order
    result, output = execute(tmp_path, store, ref, change=change)
    assert result['status'] == 'rejected'
    assert model_runs.inspect_run(output)[2]['status'] == 'rejected'
    assert not (output/'native').exists()
