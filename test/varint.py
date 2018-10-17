#
# SQLite4 varint
#
# Copyright defined in LICENSE.txt
#

def encode(num):

    if num < 0:
        raise ValueError("The number is negative")

    if num <= 240:
        result = chr(num)

    elif num <= 2287:
        num -= 240
        result = chr((num >> 8) + 241) + chr(num % 256)

    elif num <= 67823:
        num -= 2288
        result = chr(249) + chr(num >> 8) + chr(num % 256)

    else:

        if num > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("The number is bigger than an unsigned 64-bit integer")

        # convert the 64-bit number to a buffer in big endian
        buf = ''
        shift = 56
        while shift >= 0:
            buf += chr(num >> shift & 0xFF)
            shift -= 8

        # check how many zeros in the beginning
        start = 0
        for i in range(0, 8):
            if ord(buf[i]) == 0:
                start += 1
            else:
                break

        # get the number of used bytes
        num_bytes = 8 - start

        # build the result
        result = chr(247 + num_bytes) + buf[start:8]


    return result



def decode(buf):
    size = len(buf)
    if size < 1: raise ValueError("Invalid varint")
    first = ord(buf[0])

    if first <= 240:
        result = first
        num_bytes = 1

    elif first < 249:
        if size < 2: raise ValueError("Invalid varint")
        second = ord(buf[1])
        result = 240 + ((first - 241) * 256) + second
        num_bytes = 2

    elif first == 249:
        if size < 3: raise ValueError("Invalid varint")
        second = ord(buf[1])
        third = ord(buf[2])
        result = 2288 + (second * 256) + third
        num_bytes = 3

    else:
        num_bytes = first - 247
        if size < num_bytes + 1: raise ValueError("Invalid varint")
        result = ord(buf[1])
        for i in range(2, num_bytes + 1):
            result = (result << 8) | ord(buf[i])
        num_bytes += 1

    return (result, num_bytes)



tests = 0

def test_encode(num):
    print 'testing ', num
    buf = encode(num)
    num2 = decode(buf)[0]
    if num2 != num:
        print "FAILED!!!", num, num2
        quit()
    global tests
    tests += 1

if __name__ == '__main__':
    num = 11
    while num < 0xFFFFFFFFFFFFFFFF:
        test_encode(num)
        num *= 3
    print 'OK'
    print tests, 'tests'
