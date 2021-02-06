from collections import namedtuple


Element = namedtuple('Element', ('level', 'tag', 'value', 'pointer'))
Parents= namedtuple('Parents', ('father', 'mother'))

class UnKnown:
    __slots__ = ()

    def __str__(self): 
        return "Unknown"

    def __repr__(self): 
        return "Unknown"

Unknown = UnKnown()

def get_next_element(line):
    ele = line.split(None, 1)
    if len(ele) == 1:
        return ele[0], None
    else:
        return ele[0], ele[1]


def gedcom_line_to_element(value):
    pointer = None
    #
    level, value = get_next_element(value)
    #
    tag, value = get_next_element(value)
    #
    if '@' in tag:
        pointer = tag
        tag, value = get_next_element(value)

    if value is not None:
        value = value.rstrip()

    return Element(int(level), tag.lower(), value, pointer)


def parse_gedcom(filename):
    with open(filename, 'r') as fh:
        elements = [gedcom_line_to_element(line) for line in fh if line.strip() != '']

    # 
    level_zeros = []
    current = None
    for element in elements:
        if element.level == 0:
            current = GedcomElement.from_element(element)
            level_zeros.append(current)
        else:
            assert current is not None, "no elements with level >0 before the first 0 level element!"
            current += element
    return level_zeros


class GedcomElement:

    _name = None

    _subclasses = {}

    def __init_subclass__(cls, **kwargs):
        if cls._name is None:
            raise Exception(f"Please specify _name for cls '{cls.__name__}'")
        GedcomElement._subclasses[cls._name.lower()] = cls

    def __init__(self, level, tag, value, pointer):
        self._children = self._default_children()
        self._icurrent = None
        self._name = self._check_name(tag)
        self._value = value
        self._pointer = pointer
        self._level = level

    @property
    def value(self):
        return self._value

    @property
    def level(self):
        return self._level

    @property
    def pointer(self):
        return self._pointer

    @property
    def tag(self):
        return self._name

    @classmethod
    def from_element(cls, element):
        if element.tag in cls._subclasses:
            cls = cls._subclasses[element.tag]
        return cls(element.level, element.tag, element.value, element.pointer)

    def _add(self, element):
        assert self._name == element.tag
        if isinstance(self._value, str):
            self._value = [self._value]
        self._value.append(element.value)

    def __iadd__(self, rhs):
        assert isinstance(rhs, Element), "Can only add object of type 'Element'"
        if rhs.level < self.level:
            return self # do nothing
        if rhs.level == self.level:
            if self.multi is True:
                self._add(rhs)
            return self # do nothing
        if rhs.level == self.level + 1:
            if self._is_child(rhs):
                if rhs.tag in self._children:
                    if self._children[rhs.tag] is not None:
                        self._children[rhs.tag]._add(rhs)
                        return self
                self._children[rhs.tag] = GedcomElement.from_element(rhs)
                self._icurrent = self._children[rhs.tag]
            else:
                self._icurrent = None
        else:
            if self._icurrent is not None:
                self._icurrent += rhs
        return self

    def _check_name(self, tag):
        if self._name is not None:
            assert self._name == tag
        return tag

    def _default_children(self):
        return {}

    def _is_child(self, rhs):            
        return True

    def as_str(self):
        value = ''
        if self._value is not None:
            value = ' ' + to_str(self._value)
        if self._pointer is None:
            return f"{self._level} {self._name.upper()}{value}"
        return f"{self._level} {self._pointer} {self._name.upper()}{value}"

    def __str__(self): 
        return self.as_str()

    def __repr__(self): 
        return self.as_str()

    def __getattr__(self, key):
        if key in self._children:
            return self._children[key]

def to_str(ele):
    if isinstance(ele, str):
        return ele
    return " ".join(ele)


class HeadGedcom(GedcomElement):
    _name = 'head'

class DateGedcom(GedcomElement):
    _name = 'date'


class PlaceGedcom(GedcomElement):
    _name = 'plac'


class SexGedcom(GedcomElement):
    _name = 'sex'


class SurnameGedcom(GedcomElement):
    _name = 'surn'


class GivennameGedcom(GedcomElement):
    _name = 'givn'


class BirthdayGedcom(GedcomElement):
    _name = 'birt'


class BurialGedcom(GedcomElement):
    _name = 'buri'


class DeathGedcom(GedcomElement):
    _name = 'deat'


class FamilySpouseGedcom(GedcomElement):
    _name = 'fams'
    multi = True


class FamilyChildGedcom(GedcomElement):
    _name = 'famc'
    multi = True

class MarriageGedcom(GedcomElement):
    _name = 'marr'


class FamilyGedcom(GedcomElement):
    _name = 'fam'

    def get_husband(self):
        if self.husb.value is None:
            return Unknown
        return self.husb.value

    def get_wife(self):
        if self.wife.value is None:
            return Unknown
        return self.wife.value

    def get_children(self):
        if self.chil.value is None:
            return []
        return self.chil.value


class IndividualGedcom(GedcomElement):
    _name = 'indi'

    def get_parents(self, families):
        #
        if 'famc' not in self._children:
            return Parents(Unknown, Unknown)
        #
        famc = self._children['famc'].value
        #
        if isinstance(famc, list):
            famc = famc[0].strip()
        else:
            famc = famc.strip()
        #
        family = families.get(famc)
        if family is None:
            return Parents(Unknown, Unknown)
        # 
        return Parents(family.get_husband(), family.get_wife())


class PointerDict(dict):

    def __getitem__(self, key):
        if key.startswith('@'):
            return super().__getitem__(key)
        else:
            key = f"@{key}@"
            return super().__getitem__(key)

class Gedcom:

    def __init__(self, filename):
        self.elements = parse_gedcom(filename)
        self.families = PointerDict({ele.pointer: ele for ele in self.elements
                                     if ele.tag == 'fam'})
        self.people = PointerDict({ele.pointer: ele for ele in self.elements
                                   if ele.tag == 'indi'})

    def get_direct_line(self, key):            
        #
        families = self.families
        direct_line = []
        parents = [self.people[key].get_parents(families)]
        while len(parents) != 0:
            nparents = []
            for (father, mother) in parents:
                if father is not Unknown:
                    direct_line.append(father)
                    nparents.append(self.people[father].get_parents(families))
                if mother is not Unknown:
                    direct_line.append(mother)
                    nparents.append(self.people[mother].get_parents(families))
            parents = nparents
        return direct_line
        

    def print(self):
        for ele in self.elements: 
            print_children(ele)



def print_children(ele):
    print(ele)
    for ele in ele._children.values():
        if ele is not None:
            print_children(ele)


gedcom = Gedcom('example.gedcom')
print(gedcom.get_direct_line('@I3@'))
