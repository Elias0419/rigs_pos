import subprocess


def run_app():
    script_path = "main.py"

    while True:
        result = subprocess.run(["../0/bin/python", script_path])

        if result.returncode != 42:
            break


if __name__ == "__main__":
    run_app()