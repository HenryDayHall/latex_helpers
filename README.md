# Sort citations
Sort of your LaTeX citations the easy way.
Performs basic maintenance on the `.bib` file, to make it's code look pretty.

- Fixes the indentation and spacing of entries.
- Makes all months numeric to avoid those pesky errors.
- Changes the citation keys to the inspire key where possible, or mimics the inspire format when not found.
- Sorts the citations in the `.bib` file to match the order they appear in the `.tex` file.

You can run it like;
```
ipython3 sort_citations.py <list of files that includes .bib file .tex file and .aux file>
```
If all your `.bib`, `.tex` and `.aux` files are in the same directory, then just stick `sort_citations.py` in that directory and do;

```
ipython3 sort_citations.py *
```
It will ignore any files that are not `.bib`, `.tex` or `.aux`.

The updates do not overwrite your files, they create new versions with the suffix `.sorted`.
You should check the changes before replacing your files with these new versions.
If you don't back up/use version control on your LaTeX source anyway, then you are a braver person than I am.
