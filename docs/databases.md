# Databases

matchmakeo makes use of a geospatial database to store footprint metadata and make efficient geospatial queries.

Supported geospatial database types are:

+ [PostGIS](https://postgis.net/) - arguably the most common geospatial database, an extension to [PostgreSQL](https://www.postgresql.org/).
+ [SpatiaLite](https://www.gaia-gis.it/fossil/libspatialite/index) - a simple, file-based database, an extension to [SQLite](https://sqlite.org/).

Some information on setting up each of these can be found below.

## PostGIS

There are too many ways to set up or get access to a PostGIS database to list here, perhaps you're running in the cloud and can set one up with your cloud provider, or you're working at an institution where a database administrator can set one up for you on your institution's network.

### In a container

#### docker :fontawesome-brands-docker:

The most hands-off way of setting up a local PostGIS database is using [docker](https://www.docker.com/get-started/).

To launch a local container with a [PostGIS image](https://hub.docker.com/r/postgis/postgis), this command is a good starting point:

```sh
docker run \
    --name matchmakeo-db \
    --volume ./data/db:/var/lib/postgresql/data \
    -p 5432:5432 \
    -e POSTGRES_DB=matchmakeo \
    -e POSTGRES_PASSWORD=password \
    -d --rm postgis/postgis
```

This will launch a postgis container named `matchmakeo-db` with a database named `matchmakeo` using the default username `postgres`, with data stored at local disk location `./data/db` - run `mkdir -p ./data/db` if you don't already have this location.

#### apptainer

!!! question "help!"
    We're looking for feedback on this section! [Help us out!](contributing.md)

On many HPC systems, docker containers are not permitted and the alternative container approach is using _apptainer_ (formerly known as _singularity_), a very similar tool to docker.

You should consult with your HPC administrators and/or documentation before using containers on HPC, but here's the basic procedure:

1.  Convert the official Docker Hub PostGIS image into an Apptainer `.sif` file:

    ```bash
    apptainer pull postgis.sif docker://postgis/postgis:latest
    ```

2.  Create some directories in your HPC workspace, here represented by $SCRATCH, for your database to use. Check with your HPC administrator where is the best location to use.

    ```bash
    mkdir -p $SCRATCH/pg_data $SCRATCH/pg_run
    ```

3. If this is your first time setting up this database, initialize the database cluster layout inside that folder; and also define username, password and database name:

    ```bash
    apptainer run \
    --cleanenv \
    --env APPTAINERENV_POSTGRES_USER="my_user" \
    --env APPTAINERENV_POSTGRES_PASSWORD="my_secure_password" \
    --env APPTAINERENV_POSTGRES_DB="my_spatial_db" \
    --bind $SCRATCH/pg_data:/var/lib/postgresql/data \
    --bind $SCRATCH/pg_run:/var/run/postgresql \
    postgis.sif
    ```

4. Run the container persistently in the background:

    ```bash
    apptainer instance start \
        --cleanenv \
        --bind $SCRATCH/pg_data:/var/lib/postgresql/data \
        --bind $SCRATCH/pg_run:/var/run/postgresql \
        postgis.sif \
        matchmakeo-db \
        postgres -D /var/lib/postgresql/data -h 0.0.0.0 -p 5432
    ```

    + `instance start`: Tells Apptainer to run this container persistently in the background.
    + `matchmakeo-db`: The custom name assigned to this specific running instance.
    + `--cleanenv`: Erases your host HPC environment variables inside the container to prevent software version conflicts.
    + `-h 0.0.0.0`: Tells Postgres to listen on all network interfaces of the compute node, allowing your batch jobs or scripts to connect to it.
    + `-p 5432`: binds to this port number, you may need to use a different one as this is the default for postgres.

5. Connect with the database inside your python scipt:

    ```python
    from matchmakeo.databases import PostGISDatabase

    database = PostGISDatabase(
        username="my_user", # as defined earlier
        password="my_secure_password", # as defined earlier
        database="my_spatial_db", # the default database name
        host="localhost", # if running on the same host/node as the database
        port=5432, # the port in the above step
    )
    ```

    !!! note
        If running interactively or inside a Slurm script, get the node name with the `hostname` command.

        Or in your python script

        ```python
        import socket
        print(socket.gethostname())
        ```

9. Stop the container when you're done

    ```bash
    apptainer instance stop matchmakeo-db
    ```

### Connection details
Whichever method you use, to tell matchmakeo to connect to your database, you'll need the following connection details:

+ database user
+ database user's password
+ hostname - if you're running locally this may be `localhost` or `127.0.0.1` or the name given to your docker container for example,
+ port - for postgres/gis this is often `5432` by default, but might be different for a number of reasons.

For example, in your python script:

```python
from matchmakeo.databases import PostGISDatabase

database = PostGISDatabase(
    username="my_user", # as defined earlier
    password="my_secure_password", # as defined earlier
    database="my_spatial_db", # the default database name
    host="localhost", # if running on the same host/node as the database
    port=5432, # the port in the above step
)
```

## SpatiaLite

!!! question "help!"
    We're looking for feedback on this section! Help us out!

SpatiaLite is less performant than PostGIS, but can be simpler in some cases since it doesn't require a server as SQLite/Spatialite databases are simply files.

However, installing SpatiaLite is poorly documented by the official project at present, we've tried our best to summarise the installation and setup details for the most common platforms below. Alternatively, there are helpful guides online (from the [django project](https://docs.djangoproject.com/en/6.0/ref/contrib/gis/install/spatialite/) for example).

### Setup

#### Part 1: Installing SpatiaLite
<!-- tabs -->
=== "Linux :fontawesome-brands-linux:"

    On Linux, SpatiaLite can be installed directly through your system's package manager.

    Install SQLite3, the SpatiaLite extension library, and the SpatiaLite CLI tools:

    **Ubuntu/Debian/Mint**
    ```sh   
    sudo apt update
    sudo apt install sqlite3 libspatialite-dev spatialite-bin spatialite-gui
    ```

    or on **Fedora/RHEL**
    ```sh
    sudo dnf install sqlite spatialite-tools libspatialite spatialite-gui
    ```

=== "macOS :fontawesome-brands-apple:"

    The cleanest way to manage SpatiaLite on macOS is via **Homebrew**. If you do not have Homebrew installed, set it up first from [brew.sh](https://brew.sh/).

    1. Open your terminal and install the SpatiaLite tools package:  
        ```sh
        brew install spatialite-tools
        ```

    2. If you also want a graphical interface to browse your database, install the GUI version via Homebrew Cask (or use QGIS):  
        ```sh  
        brew install \--cask spatialite-gui
        ```

=== "Windows :fontawesome-brands-windows:"

    Because Windows lacks a native package manager like Linux, you will download pre-compiled binaries from the official Gaia-SIDS repository.

    1. Create a dedicated folder on your computer where you want to keep the tools (e.g., `C:\spatialite\`).  
    2. Go to the [SpatiaLite Binaries Page](http://www.gaia-gis.it/gaia-sins/index.html).  
    3. Download the latest stable **spatialite-tools** ZIP package for Windows 64-bit (e.g., `spatialite-tools-X.X.X-win-amd64.zip`).
    4. Extract the contents of the ZIP file directly into your `C:\spatialite\` folder.  
    5. *(Optional)* To access the commands easily from any command prompt, add `C:\spatialite\` to your system's **Environment PATH Variables**:  
        * Search for "Environment Variables" in your Windows Start Menu.  
        * Edit the Path variable under User or System variables and add `C:\spatialite\`.

#### Part 2: Creating a SpatiaLite Database

There are two primary methods to initialize a SpatiaLite database: using the command-line interface (CLI) or using the Graphical User Interface (GUI).

##### Method A: The Command-Line Interface (CLI)

The spatialite executable automatically creates a SQLite file and initializes it with the thousands of geographic reference system rows required for spatial geometry.

1. Open your terminal (Linux/macOS) or Command Prompt/PowerShell (Windows).  
2. Run the tool followed by the name of the database file you wish to create:  
   ```sh  
   spatialite sample_gis.sqlite
   ```

3. You will enter the SpatiaLite interactive shell environment. You should see an output similar to this:  
   ```
   SpatiaLite version ..: 5.x.x  
   SQLite version ......: 3.x.x  
   spatialite\>
   ```

##### Method B: The Graphical User Interface (GUI)

If you prefer a visual interface, you can use the spatialite-gui application installed in Part 1\.

1. Launch **SpatiaLite GUI** from your applications menu or type spatialite-gui in your terminal.  
2. In the top-left menu, navigate to **Files** \-\> **Creating a New SQLite DB**.  
3. Choose your destination directory, type a filename (e.g., visual\_gis.sqlite), and click **Save**.  
4. The application will generate the database and completely populate the internal metadata automatically.

