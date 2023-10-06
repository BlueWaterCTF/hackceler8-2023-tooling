
from z3 import *

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
    assert mod == 2
    return sum(inps)

def Multiply(inps, mod):
    assert mod == 2
    prod = inps[0]
    for v in inps[1:]:
        prod *= v
    return prod

def Invert(inp, mod):
    return (mod - 1) - inp

def Negate(inp, mod):
    return URem(-inp, mod)

def Constant(value):
    return value

def Toggle(values, index):
    assert values == [0, 1]
    result = values[0]
    for i, value in enumerate(values[1:]):
        result = If(index == (i+1), value, result)
    return result

s = Solver()

def Int(name):
    return BitVec(name, 1)

c1 = Int("c1")
t0 = Int("t0")
add0 = Int("add0")
t1 = Int("t1")
add1 = Int("add1")
t2 = Int("t2")
add2 = Int("add2")
t3 = Int("t3")
add3 = Int("add3")
t4 = Int("t4")
add4 = Int("add4")
t5 = Int("t5")
add5 = Int("add5")
t6 = Int("t6")
add6 = Int("add6")
t7 = Int("t7")
add7 = Int("add7")
t8 = Int("t8")
add8 = Int("add8")
t9 = Int("t9")
add9 = Int("add9")
t10 = Int("t10")
add10 = Int("add10")
t11 = Int("t11")
add11 = Int("add11")
t12 = Int("t12")
add12 = Int("add12")
t13 = Int("t13")
add13 = Int("add13")
t14 = Int("t14")
add14 = Int("add14")
t15 = Int("t15")
add15 = Int("add15")
s.add(c1 == Constant(value=1))
#t0_index = Int("t0_index")
#s.add(t0_index >= 0)
#s.add(t0_index < 2)
#s.add(t0 == Toggle(values=[0, 1], index=t0_index))
##s.add(add0 == Add(inps=[t0, t1, t2, c1], mod=2))
s.add(add0 == Add(inps=[t2, t4, t5, t6, t10, t11, t14, c1], mod=2))
s.add(add1 == Add(inps=[t0, t5, t9, t10, t11, t12, t13, t14, c1], mod=2))
s.add(add2 == Add(inps=[t0, t1, t3, t4, t5, t6, t8, t9, t10, t12, t13, t14, c1], mod=2))
s.add(add3 == Add(inps=[t0, t1, t3, t4, t5, t10, t13, t14, c1], mod=2))
s.add(add4 == Add(inps=[t2, t4, t6, t8, t9, t11, t15, c1], mod=2))
s.add(add5 == Add(inps=[t4, t7, t10, t11, t14, t15, c1], mod=2))
s.add(add6 == Add(inps=[t1, t3, t4, t8, t9, t11, t12, t14, t15, c1], mod=2))
s.add(add7 == Add(inps=[t0, t2, t4, t8, t10, t11, t13, c1], mod=2))
s.add(add8 == Add(inps=[t0, t2, t5, t7, t10, c1], mod=2))
s.add(add9 == Add(inps=[t2, t3, t7, t8, t12, c1], mod=2))
s.add(add10 == Add(inps=[t0, t1, t3, t4, t5, t6, t7, t8, t9, t15, c1], mod=2))
s.add(add11 == Add(inps=[t0, t1, t8, t9, t10, c1], mod=2))
s.add(add13 == Add(inps=[t0, t3, t5, t6, t7, t11, t12, t13, c1], mod=2))
s.add(add14 == Add(inps=[t0, t2, t4, t5, t9, t10, t14, t15, c1], mod=2))
s.add(add15 == Add(inps=[t0, t3, t4, t6, t7, t10, t11, t12, t14, t15, c1], mod=2))

s.add(add12 == Add(inps=[t2, t3, t7, t12, t14, t15, c1], mod=2))

s.add(add0 == 0)
s.add(add1 == 0)
s.add(add2 == 0)
s.add(add3 == 0)
s.add(add4 == 0)
s.add(add5 == 0)
s.add(add6 == 0)
s.add(add7 == 0)
s.add(add8 == 0)
s.add(add9 == 0)
s.add(add10 == 0)
s.add(add11 == 0)
#s.add(add12 == 0)
s.add(add13 == 0)
s.add(add14 == 0)
s.add(add15 == 0)

# YOUR Z3 STATEMENTS GO HERE
# s.add(my_output_i_wanna_solve_for == 31337)

result = s.check()
print(result)
assert result == sat
m = s.model()


print("c1 =", m.eval(c1).as_long())
print("t0 =", m.eval(t0).as_long())
print("add0 =", m.eval(add0).as_long())
print("t1 =", m.eval(t1).as_long())
print("add1 =", m.eval(add1).as_long())
print("t2 =", m.eval(t2).as_long())
print("add2 =", m.eval(add2).as_long())
print("t3 =", m.eval(t3).as_long())
print("add3 =", m.eval(add3).as_long())
print("t4 =", m.eval(t4).as_long())
print("add4 =", m.eval(add4).as_long())
print("t5 =", m.eval(t5).as_long())
print("add5 =", m.eval(add5).as_long())
print("t6 =", m.eval(t6).as_long())
print("add6 =", m.eval(add6).as_long())
print("t7 =", m.eval(t7).as_long())
print("add7 =", m.eval(add7).as_long())
print("t8 =", m.eval(t8).as_long())
print("add8 =", m.eval(add8).as_long())
print("t9 =", m.eval(t9).as_long())
print("add9 =", m.eval(add9).as_long())
print("t10 =", m.eval(t10).as_long())
print("add10 =", m.eval(add10).as_long())
print("t11 =", m.eval(t11).as_long())
print("add11 =", m.eval(add11).as_long())
print("t12 =", m.eval(t12).as_long())
print("add12 =", m.eval(add12).as_long())
print("t13 =", m.eval(t13).as_long())
print("add13 =", m.eval(add13).as_long())
print("t14 =", m.eval(t14).as_long())
print("add14 =", m.eval(add14).as_long())
print("t15 =", m.eval(t15).as_long())
print("add15 =", m.eval(add15).as_long())