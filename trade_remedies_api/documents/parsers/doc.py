import subprocess
import errno


def antiword(path):
    try:
        pipe = subprocess.Popen(
            ["./bin/antiword/antiword", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise Exception(path)
    stdout, stderr = pipe.communicate()

    if pipe.returncode != 0:
        raise Exception(stderr)

    return stdout, stderr


def parse(document):
    stdout, stderr = antiword(document.file)
    return stdout
