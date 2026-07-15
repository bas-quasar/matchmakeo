# Downloading footprints

## Example script

```python
from matchmakeo.catalogues import NasaCMR
from matchmakeo.databases import PostGISDatabase
from matchmakeo.queryset import NasaCMRQueryset
from matchmakeo import Product

# define your database object with the connection details
database = PostGISDatabase(
    username="postgres",
    password="password",
    database="matchmakeo",
    host="localhost",
    port=5432,
)

# make an instance of the catalogue object corresponding to which catalogue you want to download from
catalogue = NasaCMR(
    client_id="my_name", #NasaCMR takes a client_id as recommended by CMR
)

# define a queryset obect to filter the temporal and spatial bounds of your download
# some catalogues have a corresponding queryset type, others just use the base Queryset
queryset = NasaCMRQueryset(
    start_date="2020-01-01",
    end_date="2020-01-31",
    page_size=200,
    lat_max=-70,
    lat_min=-90,
    lon_max=180,
    lon_min=-180,
)

# define a product object corresponding to the data product you want to download
# the name argument defines which product is downloaded
# table_name defines the name of the database table that these downloads are inserted into
product = Product(
    name="MOD021KM",
    table_name="modis_aqua",
)

# run the download, passing in the product, queryset and database objects as arguments
catalogue.download_footprints(
    product=product,
    queryset=queryset,
    database=database,
    # optionally set dry run to be True, each catalogue behaves differently but nothing will be inserted into the database if so
    # when dry_run=True database can be None, so you can run without a database set up
    # dry_run=True,
)
```


## Running on HPC

When running as a batch job on HPC there are a few considerations to make:

+ Ensure that your python virtual environment has the right optional dependencies installed for the type of database and catalogue(s) you're using, e.g.
    + Databases
        + For PostGIS install `psycopg>3` or install matchmakeo with this optional dependency with `pip install git+https://github.com/bas-quasar/matchmakeo.git[postgis]`
        + For spatialite install the `spatialite` python package, or `pip install git+https://github.com/bas-quasar/matchmakeo.git[spatialite]`
    + Catalogues
        + NASA CMR requires no special dependencies,
        + EarthEngine requires `earthengine-api`, either `pip install earthengine-api` or `pip install git+https://github.com/bas-quasar/matchmakeo.git[earthengine]`
        + JAXA G-Portal requires `gportal`, either `pip install gportal` or `pip install git+https://github.com/bas-quasar/matchmakeo.git[gportal]`
    + Note that multiple optional dependencies can be installed at the same time, e.g. `pip install git+https://github.com/bas-quasar/matchmakeo.git[spatialite,earthengine]`
    + Or add these to your requirements.txt file or similar as `git+https://github.com/bas-quasar/matchmakeo.git[spatialite,earthengine]`
+ Ensure that you are using a non-interactive form of authentication for the catalogue(s) you're downloading from,
    + NASA CMR - currently no form of authentication supported,
    + EarthEngine - use a service account, see [Catalogues > EarthEngine > Authentication](catalogues.md#ee-auth),
    + JAXA G-portal - set via environment variables, see [Catalogues > JAXA G-Portal > Authentication](catalogues.md#gportal-auth).
+ Make sure that you have a database set up and running to accept your downloaded footprints.
    + Spatialite
        +  On most HPC systems you will need to install spatialite and its dependencies, discuss with your HPC's administrators, it may be more simple to run PostGIS in a container instead,
    + PostGIS
        + Managed database: discuss with your HPC's administrators, one option may be for them to add a database to an existing managed cluster,
        + Container: most HPC systems will support some kind of container runtime, i.e. docker, apptainer or podman. Ask your HPC's administrators which is preferable. Also see below.


### Running a PostGIS database in a container under slurm

Depending on your HPC system's preferred container system, one of the following approaches may be appropriate. We use SLURM below as an example HPC queue system, but other systems such as SGE will have similar approaches.

Essentially your batch script will have:

1. The usual batch script headers setting your job options,
1. Any module loading/purging needed before your job starts,
1. Manage your python virtual environment, e.g. activate your conda environment or venv,
1. Start up your database container, in the background, running persistently, so it keeps being available whilst you run your download,
1. Run a script containing your matchmakeo footprint download,
1. Once finished, shut down your container.

We recommend using the `trap` command as below to gracefully stop your container if your python script exits due to an error.

=== "docker"

    ```bash
    #!/bin/bash
    #SBATCH --job-name=docker_job
    #SBATCH --time=01:00:00
    # any other SBATCH header lines

    # stop the batch script if any step causes an error
    set -e

    # define a cleanup function
    cleanup() {
        echo "Stopping and removing Docker container..."
        docker stop matchmakeo-db || true
        docker rm matchmakeo-db || true
    }

    # run that cleanup function if the script exits or errors out
    trap cleanup EXIT SIGTERM

    # Start the container in detached mode (-d)
    docker run \
        --name matchmakeo-db \
        --volume ./data/db:/var/lib/postgresql/data \
        -p 5432:5432 \
        -e POSTGRES_DB=matchmakeo \
        -e POSTGRES_PASSWORD=password \
        -d --rm postgis/postgis

    # Run the Python script
    python my_matchmakeo_script.py
    ```

=== "apptainer"

    ```bash
    #!/bin/bash
    #SBATCH --job-name=docker_job
    #SBATCH --time=01:00:00
    # any other SBATCH header lines

    # stop the batch script if any step causes an error
    set -e

    # define a cleanup function
    cleanup() {
        echo "Stopping and removing Docker container..."
        apptainer instance stop matchmakeo-db || true
    }

    # run that cleanup function if the script exits or errors out
    trap cleanup EXIT SIGTERM

    # Start the container in detached mode
    apptainer instance start \
        --cleanenv \
        --env APPTAINERENV_POSTGRES_USER="my_user" \
        --env APPTAINERENV_POSTGRES_PASSWORD="my_secure_password" \
        --env APPTAINERENV_POSTGRES_DB="my_spatial_db" \
        --bind $SCRATCH/pg_data:/var/lib/postgresql/data \
        --bind $SCRATCH/pg_run:/var/run/postgresql \
        postgis.sif matchmakeo-db

    # Run the Python script
    python my_matchmakeo_script.py
    ```
