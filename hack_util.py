def shifted_keycode(keycode):
    # Alphabets: Convert lowercase to uppercase
    if 0x61 <= keycode <= 0x7A:
        return keycode - 0x20

    # Numbers and their shifts
    shift_map_numbers = {
        0x30: 0x29,  # 0 to )
        0x31: 0x21,  # 1 to !
        0x32: 0x40,  # 2 to @
        0x33: 0x23,  # 3 to #
        0x34: 0x24,  # 4 to $
        0x35: 0x25,  # 5 to %
        0x36: 0x5E,  # 6 to ^
        0x37: 0x26,  # 7 to &
        0x38: 0x2A,  # 8 to *
        0x39: 0x28   # 9 to (
    }

    if keycode in shift_map_numbers:
        return shift_map_numbers[keycode]

    # Common symbol shifts
    shift_map_symbols = {
        0x2C: 0x3C,  # , to <
        0x2E: 0x3E,  # . to >
        0x2F: 0x3F,  # / to ?
        0x3B: 0x3A,  # ; to :
        0x27: 0x22,  # ' to "
        0x5B: 0x7B,  # [ to {
        0x5D: 0x7D,  # ] to }
        0x5C: 0x7C,  # \ to |
        0x60: 0x7E,  # ` to ~
        0x2D: 0x5F   # - to _
    }

    return shift_map_symbols.get(keycode, keycode)

z3_preamble = '''
from z3 import *

BITVEC_SIZE=64

def Int(x):
    return BitVec(x, BITVEC_SIZE)

def Buffer(inp):
    return inp

def Max(inps):
    m = inps[0]
    for v in inps[1:]:
        m = If(v > m, v, m)
    return m

def Min(inps):
    m = inps[0]
    for v in inps[1:]:
        m = If(v < m, v, m)
    return m

def Add(inps, mod):
    total = sum(inps)
    return URem(total, mod)

def Multiply(inps, mod):
    prod = inps[0]
    for v in inps[1:]:
        prod *= v
    return URem(prod, mod)

def Invert(inp, mod):
    return (mod - 1) - inp

def Negate(inp, mod):
    return URem(-inp, mod)

def Constant(value):
    return value

def Toggle(values, index):
    result = BitVecVal(values[0],BITVEC_SIZE)
    for i, value in enumerate(values[1:]):
        result = If(index == (i+1), BitVecVal(value,BITVEC_SIZE), result)
    return result

def LogicDoor(inp):
    return inp

s = Solver()
'''

z3_epilogue = '''

# YOUR Z3 STATEMENTS GO HERE
# s.add(my_output_i_wanna_solve_for == 31337)

result = s.check()
print(result)
assert result == sat
m = s.model()
'''