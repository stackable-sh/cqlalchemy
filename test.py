#!/usr/bin/env python

"""
Author: @Iroiso
Description: 
A simple utility for running all the selected or all the tests in the tests package
At prompt change to the project directory. 

To run all tests type:

```bash
$./test.py 
```
To run specific tests type (you may use glob patterns to simplify things for yourself):

```bash
$./test.py testrecor* testproper*   
```

"""
import sys
from glob import glob
from unittest import TextTestRunner, TestLoader, TestSuite

sys.path.extend(["./cqlalchemy",])

def find(*argument):
    """Discovers tests from the tests package and returns them"""
    base = "tests/"
    suite = TestSuite()
    if not argument:
        suite = TestLoader().discover(base, pattern="*.py")
    elif argument:
        for i in argument:
            found = TestLoader().discover(start_dir=base, pattern=i)
            suite.addTest(found)
    return suite


if __name__ == "__main__":
    """Find unittests and run them"""
    arguments = sys.argv[1:]
    suite = find(*arguments)
    runner = TextTestRunner(verbosity=2)
    runner.run(suite)
