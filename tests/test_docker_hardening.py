from pathlib import Path


def test_docker_runtime_does_not_run_as_root():
    text=Path('Dockerfile').read_text(encoding='utf-8')
    assert 'useradd --create-home --uid 10001 notsip' in text
    assert '\nUSER notsip\n' in text
    assert text.rfind('USER notsip') < text.rfind('CMD ["python","-m","notsip"]')
