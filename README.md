## Mat!
"What's for lunch" script for restaurants around Grönsakstorget, Gothenburg

## Usage
```bash
./mat.py -p <plugin directory>
```

If no plugin directory is specified, `$HOME/.mat` is used if it exists.
If it doesn't, `./plugins` is used instead.

### Dependencies
For restaurants with PDF menus (Bee): `PyMuPDF`
For all other restaurants: `bs4`

If some restaurants don't show up, chances are you haven't installed one
of the above dependencies.

### Contributing
Is your favourite restaurant missing?
[File a bug report](https://github.com/valderman/mat/issues/new)
or submit a pull request!

### Plugin API
Plugins need to export two functions:
* `name()`, returning the name of the restaurant as a string, and
* `food(api, date)`, returning a list of `Food` objects representing
  the restaurants offerings on the given date.

`Food` objects are created using the function
`api.food(dish, dish_description)`.

For convenience, `api` also contains the following:
* `soup`: reexport of `bs4.BeautifulSoup`
* `requests`: reexport of `requests`
