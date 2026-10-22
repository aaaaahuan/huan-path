"""Pipeline persistence checks use temporary jobs and tracks exclusively."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.jobs = self.root / 'jobs'
        self.tracks = self.root / 'tracks'
        self.environment = patch.dict(os.environ, HUAN_PATH_JOBS_DIR=str(self.jobs),
                                      HUAN_PATH_TRACKS_DIR=str(self.tracks))
        self.environment.start()
        self.addCleanup(self.environment.stop)
        # Set the temporary environment before the module's initial mkdir.
        self.pipeline = importlib.import_module('app.pipeline')
        self.jobs.mkdir(exist_ok=True)
        replacement = patch.object(self.pipeline, 'JOBS', self.jobs)
        replacement.start()
        self.addCleanup(replacement.stop)

    def state(self, job):
        return json.loads((job / 'status.json').read_text())

    def test_track_copy_collision_identical_and_source(self):
        first = self.pipeline.create_job(filename='../route.KML', content=b'first')
        self.assertEqual(self.state(first)['track_file'], 'route.KML')
        same = self.pipeline.create_job(filename='route.KML', content=b'first')
        self.assertEqual(self.state(same)['track_file'], 'route.KML')
        self.assertEqual(len(list(self.tracks.iterdir())), 1)
        source = self.root / 'route.KML'
        source.write_bytes(b'different')
        other = self.pipeline.create_job(source=source)
        expected = f'route-{other.name}.KML'
        self.assertEqual(self.state(other)['track_file'], expected)
        self.assertEqual((self.tracks / expected).read_bytes(), b'different')
        self.assertEqual((self.tracks / 'route.KML').read_bytes(), b'first')

    def test_archive_failure_and_disabled(self):
        self.tracks.write_text('not a directory')
        with self.assertLogs(level='ERROR'):
            job = self.pipeline.create_job(filename='route.kml', content=b'original')
        self.assertNotIn('track_file', self.state(job))
        self.assertEqual((job / 'input.kml').read_bytes(), b'original')
        with patch.dict(os.environ, HUAN_PATH_TRACKS_DIR=''):
            job = self.pipeline.create_job(filename='route.kmz', content=b'zip')
        self.assertNotIn('track_file', self.state(job))

    def test_retry_rebases_normal_and_imported_paths(self):
        info = {'photo_points': [], 'warnings': [], 'name': 'route', 'epsg': 32648,
                'missing_altitude': False}
        for imported in (False, True):
            with self.subTest(imported=imported):
                job = self.pipeline.create_job(filename='route.kml', content=b'original')
                config = json.loads((self.pipeline.ROOT / 'config/features.json').read_text())
                for key, extension in [('model_stl', 'stl'), ('model_glb', 'glb')]:
                    config['houses'][key] = f'/old/jobs/job/data/house_designs/house.{extension}'
                    if imported:
                        local = job / f'data/house_designs/house.{extension}'
                        local.parent.mkdir(exist_ok=True)
                        local.write_bytes(b'model')
                config['houses']['list_file'] = '/old/jobs/job/data/photo_houses.json'
                (job / 'config.json').write_text(json.dumps(config))
                (job / 'spec.json').write_text(json.dumps({'preserve_imported_assets': imported,
                    'route': info, 'warnings': [], 'data_dir': '/old/jobs/job/data'}))
                with patch.object(self.pipeline, 'parse_track', return_value=(dict(info), [1], b'kml')), \
                     patch.object(self.pipeline, 'canonical'), \
                     patch.object(self.pipeline, 'prepare_dem'), \
                     patch.object(self.pipeline.subprocess, 'run', side_effect=RuntimeError('stop before build')):
                    self.assertFalse(self.pipeline.run_job(job))
                spec = json.loads((job / 'spec.json').read_text())
                saved = json.loads((job / 'config.json').read_text())
                self.assertEqual(spec['data_dir'], str(job / 'data'))
                self.assertEqual(saved['houses']['list_file'], str(job / 'data/photo_houses.json'))
                defaults = json.loads((self.pipeline.ROOT / 'config/features.json').read_text())
                for key in ('model_stl', 'model_glb'):
                    expected = (job / 'data/house_designs' / Path(config['houses'][key]).name
                                if imported else self.pipeline.ROOT / defaults['houses'][key])
                    self.assertEqual(saved['houses'][key], str(expected))
