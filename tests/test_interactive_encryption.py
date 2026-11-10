"""Choix manuel sur un vrai pseudo-terminal ; cron simule avec une entree sans terminal."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "/bin/bash"


class EncryptionChoice(unittest.TestCase):
    def configure(self, configured, recipients, answers=None, age_available=True):
        code = f'source "{(ROOT / "scripts/backup.sh").as_posix()}"\n'
        code += 'ENCRYPT="$TEST_ENCRYPT"; RECIPIENTS="$TEST_RECIPIENTS"\n'
        if age_available:
            code += 'age(){ :; }\n'
        else:
            code += 'command(){ [[ "$*" != "-v age" ]] && builtin command "$@"; }\n'
        if answers is None:
            # Un seul appel a read ferait echouer le test, meme si une reponse est disponible.
            code += 'read(){ echo "FORBIDDEN PROMPT" >&2; return 99; }\n'
        code += 'configure_encryption\nprintf "ENCRYPT=%s\\nRECIPIENTS=%s\\n" "$ENCRYPT" "${RECIPIENTS:-}"\n'
        env = dict(os.environ, TEST_ENCRYPT=configured, TEST_RECIPIENTS=str(recipients))
        if answers is None:
            return subprocess.run([BASH, "-c", code], input="o\n", text=True, capture_output=True, env=env, timeout=10)
        import pty
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([BASH, "-c", code], stdin=slave, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, env=env)
            os.close(slave); slave = None
            os.write(master, answers.encode())
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate(); raise
            return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        finally:
            os.close(master)
            if slave is not None: os.close(slave)

    def test_cron_uses_configuration_without_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            recipients = pathlib.Path(directory) / "recipients"
            recipients.write_text("fixture-public-recipient\n")
            for configured in ("false", "true"):
                with self.subTest(configured=configured):
                    result = self.configure(configured, recipients)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("ENCRYPT=" + configured, result.stdout)
                    self.assertNotIn("FORBIDDEN PROMPT", result.stderr)
            missing = recipients.with_name("missing")
            result = self.configure("true", missing)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("absent ou vide", result.stderr)
            self.assertNotIn("FORBIDDEN PROMPT", result.stderr)
            result = self.configure("true", recipients, age_available=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("installer age", result.stderr)
            result = self.configure("false", missing, age_available=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipIf(os.name == "nt", "Pseudo-terminal Linux")
    def test_manual_default_no_even_if_cron_encryption_enabled(self):
        result = self.configure("true", "/missing", answers="\n", age_available=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ENCRYPT=false", result.stdout)
        self.assertEqual(result.stderr.count("Voulez-vous chiffrer"), 1)
        self.assertNotIn("destinataires PUBLICS", result.stderr)

    @unittest.skipIf(os.name == "nt", "Pseudo-terminal Linux")
    def test_manual_yes_reuses_public_recipients_or_asks_once(self):
        with tempfile.TemporaryDirectory() as directory:
            recipients = pathlib.Path(directory) / "recipients"
            recipients.write_text("fixture-public-recipient\n")
            for configured, answers, prompts in ((recipients, "o\n", 0),
                                                  (recipients.with_name("missing"), "o\n" + str(recipients) + "\n", 1)):
                with self.subTest(configured=configured):
                    result = self.configure("false", configured, answers=answers)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("ENCRYPT=true", result.stdout)
                    self.assertIn("RECIPIENTS=" + str(recipients), result.stdout)
                    self.assertEqual(result.stderr.count("Voulez-vous chiffrer"), 1)
                    self.assertEqual(result.stderr.count("destinataires PUBLICS"), prompts)
            result = self.configure("false", recipients, answers="o\n", age_available=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("installer age", result.stderr)


if __name__ == "__main__": unittest.main()
