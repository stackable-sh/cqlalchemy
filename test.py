#!/usr/bin/env python
# Copyright 2026 Iroiso Ikpokonte
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
from unittest import TextTestRunner, TestLoader, TestSuite

sys.path.extend(
    [
        "./cqlalchemy",
    ]
)


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
    """Find unittests, randomize and run them in sequence to minimize side effects"""
    arguments = sys.argv[1:]
    suite = find(*arguments)
    runner = TextTestRunner(verbosity=2)
    runner.run(suite)
