# install venv module (if not yet present)
sudo apt install python3-venv

# create python virtual environment, choose location f.e. ~/.envs/qgis
python3 -m venv --system-site-packages ~/.envs/qgis
# activate virtual env
source ~/.envs/qgis/bin/activate

# install brdr and geopandas
pip install brdr
pip install geopandas

# run qgis inside virtual environment
qgis