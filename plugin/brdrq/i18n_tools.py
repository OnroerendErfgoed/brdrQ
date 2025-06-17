import logging
import os
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def update_ts_files(plugin_dir, i18n_dir):
    logging.info("Updating .ts files with pylupdate5...")

    # Verzamel alle .py en .ui bestanden
    source_files = []
    for file in os.listdir(plugin_dir):
        if file.endswith('.py') or file.endswith('.ui'):
            source_files.append(os.path.join(plugin_dir, file))

    if not source_files:
        logging.warning("Geen .py of .ui bestanden gevonden.")
        return

    for ts_file in os.listdir(i18n_dir):
        if ts_file.endswith('.ts'):
            ts_path = os.path.join(i18n_dir, ts_file)
            cmd = ['pylupdate5'] + source_files + ['-ts', ts_path]
            try:
                subprocess.run(cmd, check=True)
                logging.info(f"Bijgewerkt: {ts_file}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Mislukt: {ts_file}: {e}")

def compile_qm_files(i18n_dir):
    logging.info("Compileren van .ts naar .qm met lrelease...")

    for ts_file in os.listdir(i18n_dir):
        if ts_file.endswith('.ts'):
            ts_path = os.path.join(i18n_dir, ts_file)
            cmd = ['lrelease', ts_path]
            try:
                subprocess.run(cmd, check=True)
                logging.info(f"Gecompileerd: {ts_file}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Compilatie mislukt: {ts_file}: {e}")

if __name__ == "__main__":
    plugin_directory = os.path.dirname(os.path.abspath(__file__))
    i18n_directory = os.path.join(plugin_directory, 'i18n')

    if not os.path.exists(i18n_directory):
        logging.error("i18n-map niet gevonden.")
    else:
        update_ts_files(plugin_directory, i18n_directory)
        compile_qm_files(i18n_directory)
