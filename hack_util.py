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
