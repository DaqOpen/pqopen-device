import subprocess

def is_time_synchronized():
    try:
        output = subprocess.check_output(['chronyc', 'tracking'], encoding='utf-8')
        for line in output.splitlines():
            if line.startswith('Leap status'):
                status = line.split(':')[1].strip()
                return status.lower() == 'normal'
    except subprocess.CalledProcessError as e:
        print("Error running chronyc:", e)
    except FileNotFoundError:
        print("chronyc not installed")
    return False