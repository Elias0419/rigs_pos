import psutil
import subprocess
import time

def wait_and_restart(process_pid, script_path, python_executable):
    try:
        psutil.Process(process_pid).wait()
        subprocess.run([python_executable, script_path])
    except psutil.NoSuchProcess:
        subprocess.run([python_executable, script_path])

if __name__ == "__main__":
    # Pass the PID of the main app, the script path, and the python executable path
    main_app_pid = int(sys.argv[1])
    script_path = sys.argv[2]
    python_executable = sys.argv[3]
    wait_and_restart(main_app_pid, script_path, python_executable)
