"""Schema-backed readers for Leafcutter's native authored artifacts.

Readers consume an immutable source checkout as data. They never execute code
from that checkout; each type keeps its own reviewed extraction contract.
"""
