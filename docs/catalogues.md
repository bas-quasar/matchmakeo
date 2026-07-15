# Catalogues

Images and metadata are made available through a number of platforms, which in `matchmakeo` we call "catalogues". These are the services from which metadata is obtained. Built-in catalogue interfaces are:

+ [NASA Common Metadata Repository](https://www.earthdata.nasa.gov/about/esdis/eosdis/cmr){target="_blank"}
+ [Google EarthEngine](https://earthengine.google.com/){target="_blank"}
+ [JAXA G-Portal](https://gportal.jaxa.jp/gpr/){target="_blank"}

You can also implement your own interface to another catalogue by inheriting from `matchmakeo.catalogues.Catalogue` - more documentation to follow. Or [open an issue on GitHub](https://github.com/bas-quasar/matchmakeo/issues/new){target="_blank"} to request another catalogue interface.

Some of the same satellite data products are available through different catalogues, but you'll need to specify one for each download.

The catalogues are each represented by a class in the `matchmakeo.catalogues` module, e.g. `NasaCMR`, `EarthEngine` or `JaxaGportal`.

Some of the catalogues have a corresponding queryset class, e.g. `NasaCMRqueryset` which handle parameters which are specific to downloading from that catalogue, such as `page_size` (the number of records to download in one request).

## NASA Common Metadata Repository (CMR) {#nasacmr}
Home: <https://www.earthdata.nasa.gov/about/esdis/eosdis/cmr>

### Authentication {#nasacmr-auth}
`matchmakeo` currently does not support user authentication for NASA CMR, so only public data is accessible. If this is a feature you need, consider [contributing](contributing.md)!

### Finding products
Products can be found through <https://search.earthdata.nasa.gov>

For instance this product "MODIS/Terra Calibrated Radiances 5-Min L1B Swath 1000m V7" <https://cmr.earthdata.nasa.gov/search/concepts/C3861664481-LAADS.html>

To download footprints for this product you would need the ID, or "short name", in this case "MOD021KM".

You may also need the version, in this case it's "7".

So to define the product to download, you would use `Product(name="MOD021KM", version=7)`.

## Google EarthEngine {#ee}
Home: <https://earthengine.google.com/>

### Dependencies {#ee-deps}
Requires the `earthengine-api` package. Install either with the `[earthengine]` dependencies option when installing matchmakeo, i.e. `pip install git+https://github.com/bas-quasar/matchmakeo.git[earthengine]` or on its own with `pip install earthengine-api`.

### Authentication {#ee-auth}
Follow the guidance on earth engine access at <https://developers.google.com/earth-engine/guides/access> including creating a google cloud project.

Note that the earth engine catalogue runs the `ee.Initialize()` method. when instantiating the `matchmakeo.catalogues.EarthEngine` class.

Also note that for non-interactive execution, such as in an HPC job, you will need a service account (see <https://developers.google.com/earth-engine/guides/service_account>). Also pass the argument `service_account=True` to `EarthEngine()`.

### Finding products
The product name required by `matchmakeo.product.Product` can be found by looking for your matching product in the data catalogue at <https://developers.google.com/earth-engine/datasets/catalog>, for instance for the dataset at <https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED> you would use `Product(name="COPERNICUS_S2_SR_HARMONIZED")`.


## JAXA G-Portal {#gportal}

Home: <https://gportal.jaxa.jp/gpr/>

### Dependencies {#gportal-deps}
Requires the `gportal` package. Install either with the `[gportal]` dependencies option when installing matchmakeo, i.e. `pip install git+https://github.com/bas-quasar/matchmakeo.git[gportal]` or on its own with `pip install gportal`.

### Authentication {#grportal-auth}
1. Register for an account at <https://gportal.jaxa.jp/gpr/user/regist1>
2. Set your username and password in one of two ways:
    - Set the `GPORTAL_USERNAME` and `GPORTAL_PASSWORD` environment variables,
    - Pass them in as arguments when instantiating the `matchmakeo.catalogues.JaxaGportal` class, e.g. `catalogue = JaxaGportal(username="my_username", password="my_password")`

### Finding products
The product name required by `matchmakeo.product.Product` can be found by looking for your matching product id in the dictionary produced by `gportal.datasets()`.