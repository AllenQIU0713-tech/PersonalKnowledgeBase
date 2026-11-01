"""Launcher lifecycle checks: no live services, browser, model or formal data."""
import importlib.util
import io
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('pkb_start', Path(__file__).resolve().parents[3]/'scripts/start.py')
start = importlib.util.module_from_spec(spec)
spec.loader.exec_module(start)


class Launcher(unittest.TestCase):
    def test_missing_model_fails_before_port_check(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(start, 'port_in_use') as ports:
            with self.assertRaises(ValueError): start.preflight(Path(tmp)/'missing', Path(tmp)/'runtime')
            ports.assert_not_called()

    def test_occupied_port_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, runtime = Path(tmp)/'model', Path(tmp)/'runtime'
            model.write_bytes(b'123'); runtime.write_bytes(b'run'); runtime.chmod(0o700)
            with patch.object(start, 'MODEL_SIZE', 3), patch.object(start, 'port_in_use', return_value=True):
                with self.assertRaisesRegex(ValueError, '8765'): start.preflight(model, runtime)

    def test_wrong_model_size_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'model'; p.write_bytes(b'wrong')
            with self.assertRaises(ValueError): start.preflight(p, p)

    def test_actual_link_is_validated(self):
        link = 'http://127.0.0.1:8765/unlock?token=SYNTHETIC-token'
        self.assertEqual(start.startup_link(start.PREFIX+link+'\n'), link)
        self.assertIsNone(start.startup_link('ordinary output'))
        for bad in ['http://example.com/unlock?token=x', 'http://127.0.0.1:8765/unlock?token=x&next=evil']:
            with self.assertRaises(ValueError): start.startup_link(start.PREFIX+bad)

    def test_finished_process_is_not_signalled(self):
        process = Mock(); process.poll.return_value = 0
        with patch.object(start.os, 'killpg') as kill:
            start.stop_owned(process); kill.assert_not_called()

    def test_only_owned_process_group_is_stopped(self):
        process = Mock(pid=123456); process.poll.return_value = None
        with patch.object(start.os, 'killpg') as kill:
            start.stop_owned(process); kill.assert_called_once_with(123456, signal.SIGTERM)

    def test_hung_owned_process_is_reaped(self):
        process = Mock(pid=123456); process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('synthetic', 10), 0]
        with patch.object(start.os, 'killpg') as kill:
            start.stop_owned(process)
            self.assertEqual(kill.call_args_list[1].args, (123456, signal.SIGKILL))

    def test_model_failure_cleans_owned_process(self):
        model = Mock()
        with patch.object(start, 'preflight'), patch.object(start.subprocess, 'Popen', return_value=model), \
             patch.object(start, 'wait_model', side_effect=RuntimeError('synthetic model failed')), \
             patch.object(start, 'stop_owned') as stop, patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(RuntimeError): start.run(Path('/synthetic-not-opened'))
            stop.assert_called_once_with(model)

    def test_successful_session_cleans_app_then_model(self):
        model = Mock(); model.poll.return_value = None
        app = Mock(); app.stdout = io.StringIO(start.PREFIX+'http://127.0.0.1:8765/unlock?token=SYNTHETIC\n')
        app.wait.return_value = 0
        with patch.object(start, 'preflight'), patch.object(start.subprocess, 'Popen', side_effect=[model, app]), \
             patch.object(start, 'wait_model'), patch.object(start, 'stop_owned') as stop, \
             patch.object(start.webbrowser, 'open', return_value=True) as browser, patch('sys.stdout', new_callable=io.StringIO):
            start.run(Path('/synthetic-not-opened'))
            self.assertEqual([c.args[0] for c in stop.call_args_list], [app, model])
            browser.assert_called_once_with('http://127.0.0.1:8765/unlock?token=SYNTHETIC', new=2)

    def test_preflight_failure_never_starts_process(self):
        with patch.object(start, 'preflight', side_effect=ValueError('port busy')), \
             patch.object(start.subprocess, 'Popen') as spawn:
            with self.assertRaises(ValueError): start.run(Path('/synthetic-not-opened'))
            spawn.assert_not_called()


if __name__ == '__main__': unittest.main()
