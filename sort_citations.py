import sys, os, urllib, json
import datetime
from ipdb import set_trace as st
import numpy as np

# helper functions for text processing ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def strip_formating(string, brackets=True, quotes=True,
                    whitespace=False, whitespace_to_space=False,
                    comma=False, dot=False):
    if quotes:
        string = string.replace('"', '')
    if brackets:
        string = string.replace('{', '').replace('}', '')
    if whitespace or whitespace_to_space:
        replace_with = ' ' if whitespace_to_space else ''
        string = string.replace('\n', replace_with).replace('\t', replace_with)
        string = string.replace('\r', replace_with)
        string = string.replace(' ', replace_with)
    if comma:
        string = string.replace(',', '')
    if dot:
        string = string.replace('.', '')
    return string


def locate_closing_brace(string, opening_location, closing_brace="}"):
    opening_brace = string[opening_location]
    nesting = opening_brace != closing_brace
    num_open = 1
    for i, charicter in enumerate(string[opening_location+1:]):
        if charicter == opening_brace and nesting:
            num_open += 1
        elif charicter == closing_brace:
            num_open -= 1
            if num_open == 0:
                return opening_location + i + 1
    return -1


def month_to_numeric(bib_fields):
    if 'month' not in bib_fields:
        return bib_fields
    month = bib_fields['month']
    if isinstance(month, int):
        return str(bib_fields)
    if isinstance(month, str):
        # remove brackets
        month = strip_formating(month, whitespace=True)
        if month.isnumeric():
            return bib_fields
        try:
            month = datetime.datetime.strptime(month, "%b").month
        except ValueError:
            try:
                month = datetime.datetime.strptime(month, "%B").month
            except ValueError:
                raise ValueError(f"Cannot parse {month} as a month")
        bib_fields['month'] = str(month)
        return bib_fields
    # if we reach here it's dificult to know what the formt has done
    raise TypeError(f"Month {month} is not a str or an int, don't know how to parse")

# functions for reading latex files ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_ordered_citations(aux_path):
    with open(aux_path, 'r') as aux_file:
        text = aux_file.read()
    cite_start = "\\abx@aux@cite"
    cites = []
    untrimmed_cites = text.split(cite_start)[1:]
    for untrimmed in untrimmed_cites:
        end = locate_closing_brace(untrimmed, 0)
        if end == -1:
            raise ValueError(f"No end to citation key {untrimmed} found")
        cite = untrimmed[1: end]
        if cite not in cites:
            cites.append(cite)
    return cites


def get_bib_entries(bib_path):
    with open(bib_path, 'r') as bib_file:
        text = bib_file.read()
    bib_entries = {}
    start_key = "@"
    next_start = text.find(start_key)
    while next_start > -1:
        first_brace = text.find('{', next_start)
        closing_brace = locate_closing_brace(text, first_brace)
        bib_string = text[next_start: closing_brace+1]
        key = get_bib_entry_key(bib_string)
        bib_entries[key] = bib_string
        next_start = text.find(start_key, closing_brace)
    return bib_entries


def get_bib_entry_key(bib_string):
    try:
        key_string = bib_string.split('{', 1)[1].split(',', 1)[0]
    except IndexError:
        message = "Problem in bib string;\n" + bib_string
        raise IndexError(message)
    return key_string.strip()


def read_bib_entry(bib_entry):
    bib_entry = bib_entry.strip()
    # the entry type should be capitalised for neatness
    entry_type = bib_entry.split('@', 1)[1].split('{', 1)[0]
    entry_type = entry_type.capitalize()
    # can use existing function to get the key
    entry_key = get_bib_entry_key(bib_entry)
    # now the rest is fields
    fields_end = locate_closing_brace(bib_entry, bib_entry.find("{"), "}")
    fields = {}
    # there can be = insie titles
    # the first entry has no comma, the key starts at char 0
    field_ends = bib_entry.find(',')
    field_starts = bib_entry.find('=')
    brackets = {'"': '"', '{': '}', "'": "'"}
    while field_starts > -1 and field_ends < fields_end:
        # skip the comma
        key = bib_entry[field_ends+1 :field_starts].strip().lower()
        field_ends = field_starts + 1  # after the =
        while field_ends < fields_end:
            char = bib_entry[field_ends]
            if char in brackets:
                field_ends = locate_closing_brace(bib_entry,
                                               field_ends, 
                                               brackets[char])
            elif char == ',':
                break
            field_ends += 1
        content = bib_entry[field_starts+1: field_ends]
        # only white space is single space
        content = ' '.join(content.split())
        fields[key] = content
        field_starts = bib_entry.find('=', field_ends)
    return entry_type, entry_key, fields

# functions for talking to inspires ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_inspire_key(bib_fields, other_fields=None):
    errors = {}
    if "doi" in bib_fields:
        # can have more than 1 doi
        string = bib_fields["doi"].split(',', 1)[0]
        string = strip_formating(string, whitespace=True)
        search = f'find doi "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["doi"] = e
        # sometimes this is actually an arXiv number
        search = f'find eprint arxiv:{string}'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["arxiv"] = e
    if "eprint" in bib_fields:
        string = bib_fields["eprint"].split(',', 1)[0]
        string = strip_formating(string, whitespace=True)
        search = f'find eprint "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["eprint"] = e
    if "title" in bib_fields:
        string = bib_fields["title"]
        string = strip_formating(string, whitespace_to_space=True)
        search = f'find title "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["title"] = e
    if "author" in bib_fields:
        string = bib_fields["author"]
        string = strip_formating(string, whitespace_to_space=True,
                                 comma=True, dot=True)
        string = string.replace('and', '')
        search = f'find author "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["author"] = e
    raise ValueError(str(errors))


def _get_inspire_key(search, other_fields=None):
    if other_fields is None:
        other_fields = []
    key_tag = "system_control_number"
    out_tags = [key_tag, *other_fields]
    data = query_inspire(search, out_tags)
    if len(data) > 1:
        raise ValueError(f"Not enough unique info")
    if len(data) == 0:
        raise ValueError(f"No match found for {search}")
    key_list = data[0][key_tag]
    if isinstance(key_list, dict):
        key_list = [key_list]
    try:
        key = next(k['value'] for k in key_list
                   if k['institute'] == 'SPIRESTeX'
                   or k['institute'] == 'INSPIRETeX')
    except StopIteration:
        raise ValueError(f"No Inspires key in {key_list}")
    other = {field: data[0][field] for field in other_fields}
    return key, other


def query_inspire(search_pattern, out_tags=None):
    search_pattern = search_pattern.replace(' ', '+').replace("/", "%2F")
    url = "http://old.inspirehep.net/search?p=" + search_pattern 
    url += "&of=recjson"
    if out_tags is not None:
        if isinstance(out_tags, str):
            out_tags = [out_tags]
        url += "&ot=" + ','.join(out_tags)
    data = urllib.request.urlopen(url).read().decode()
    data = json.loads(data)
    return data

#  incase inspires is not feeling chatty today ~~~~~~~~~~~~~~~~~~~~

def fake_inspires_key(bib_fields):
    author_list = bib_fields['author'].replace(' and ', ',')
    author = author_list.split(',')[0]
    key = ''.join(filter(str.isalpha, author))
    key += ":" + bib_fields['year']
    key = strip_formating(key, dot=True, comma=True)
    key += "_unfound" + str(np.random.randint(1000))
    return key

# functions for writing latex files ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def write_new_bib(new_path, cite_order, bib_entries):
    ordered_cites = [bib_entries[key] for key in cite_order]
    cite_sep = os.linesep + os.linesep
    text = cite_sep.join(ordered_cites)
    with open(new_path, 'w') as save_file:
        save_file.write(text)


def make_bib_entry(entry_type, entry_key, fields):
    text = "@" + entry_type.capitalize() + "{"
    text += " " + entry_key + ",\n"
    longest_field_key = np.max([len(key) for key in fields])
    for key in fields:
        text += "    " + key.ljust(longest_field_key) + " = "
        text += fields[key] + ",\n"
    text += "}"
    return text


def update_entries_in_bib(new_path, cite_order, bib_entries):
    new_bib_entries = {}
    updated_key_dict = {}
    for key in bib_entries:
        entry_type, entry_key, fields = read_bib_entry(bib_entries[key])
        fields = month_to_numeric(fields)
        try:
            new_key, _ = get_inspire_key(fields)
        except ValueError:
            print(f"Didn't find {fields['title']}")
            new_key = fake_inspires_key(fields)
        if new_key not in new_bib_entries:
            new_bib_entries[new_key] = make_bib_entry(entry_type, new_key, fields)
        updated_key_dict[entry_key] = new_key
    # make sure there are no duplicates in the new cite order
    new_cite_order = []
    for key in cite_order:
        new_key = updated_key_dict[key]
        if new_key not in new_cite_order:
            new_cite_order.append(new_key)
    write_new_bib(new_path, new_cite_order, new_bib_entries)
    return updated_key_dict


def update_bib_keys_in_tex(tex_file_name, updated_dict):
    with open(tex_file_name, 'r') as tex_file:
        text = tex_file.read()
    cite_str = "\\cite{"
    cite_len = len(cite_str)
    cite_end = 0
    cite_start = text.find(cite_str)
    new_text = ""
    while cite_start > -1:
        # add the previous segment
        new_text += text[cite_end: cite_start + cite_len]
        # get the new cites
        cite_end = text.find('}', cite_start)
        cites = text[cite_start + cite_len:cite_end].split(',')
        new_cites = [updated_dict.get(c.strip(), c) for c in cites]
        # add the new cites
        new_text += ','.join(new_cites)
        cite_start = text.find(cite_str, cite_end)
    # add the last segment
    new_text += text[cite_end:]
    new_name = tex_file_name + ".sorted"
    with open(new_name, 'w') as new_file:
        new_file.write(new_text)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(f"Usage;\n > {sys.argv[0]} <All tex files, aux file and bib file>")
    else:
        tex_files = []
        for path in sys.argv[1:]:
            if not os.path.exists(path):
                continue
            if path.endswith(".aux"):
                aux_path = path
            if path.endswith(".bib"):
                bib_path = path
            if path.endswith(".tex"):
                tex_files.append(path)
        new_path = bib_path + ".sorted"
        cite_order = get_ordered_citations(aux_path)
        bib_entries = get_bib_entries(bib_path)
        updated_dict = update_entries_in_bib(new_path, cite_order, bib_entries)
        for tex_file in tex_files:
            update_bib_keys_in_tex(tex_file, updated_dict)


