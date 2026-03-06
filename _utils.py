import configparser
import logging
from typing import Final
from sqlalchemy import create_engine

_CONFIG_FILE: Final = 'config.ini'

def _get_db_config() :
	config = configparser.ConfigParser()
	config.read(_CONFIG_FILE)
	return {
		'dbname':   config.get('database', 'dbname'),
		'user':     config.get('database', 'user'),
		'password': config.get('database', 'password'),
		'host':     config.get('database', 'host'),
		'port':     config.get('database', 'port')
	}

def _get_db_engine(db_config) :
	dbname   = db_config['dbname']
	user     = db_config['user']
	password = db_config['password']
	host     = db_config['host']
	port     = db_config['port']
	
	connection_string = f'postgresql://{user}:{password}@{host}:{port}/{dbname}'
	return create_engine(connection_string)

def _read_config(section, key, default=None) :
	config = configparser.ConfigParser()
	config.read(_CONFIG_FILE)
	value = config.get(section, key)
	if value is None :
		return default
	else :
		return value

def get_data_filepath(filename) :
	return f"./{ DATA_DIR }/{ filename }"

# Function for capitalizing the first word in a string
def ucfirst(s) :
	return s[0].upper() + s[1:]

# Cross-script global constants
COLOR: Final              = _read_config('io', 'color', 'bw')
DATA_DIR: Final           = _read_config('io', 'data_dir')
CLUSTERING_DB_NAME: Final = _read_config('io', 'clustering_schema')
NEPHROPATHY_TABLE: Final  = _read_config('io', 'nephropathy_table', 'nephropathy')
RETINOPATHY_TABLE: Final  = _read_config('io', 'retinopathy_table', 'retinopathy')
FIRST_YEAR: Final       = int(_read_config('clustering', 'first_year'))
LAST_YEAR: Final        = int(_read_config('clustering', 'last_year'))
CLUSTERING_YEARS: Final = int(_read_config('clustering', 'clustering_years'))
N_CLUSTERS: Final       = int(_read_config('clustering', 'n_clusters'))
db_config: Final = _get_db_config()
db_engine: Final = _get_db_engine(db_config)

logging.basicConfig(format='%(asctime)s - %(message)s')  # Include timestamp into logs
logger: Final = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Defining what should be exported
__all__ = [name for name in globals() if not name.startswith("_")]
