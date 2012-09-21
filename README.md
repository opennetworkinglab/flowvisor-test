FlowVisor Testing Framework
Jan, 2012

License
=======

Copyright (c) 2012 The Board of Trustees of The Leland Stanford
Junior University


Getting FVTest
==============

    You can check out FVTest with git with the following command:
    # git clone git@bitbucket.org:onlab/flowvisor-test.git

Introduction
============

    This test framework(FVTest) is a Python based test framework
    and collection of test cases.
    It is meant to exercise a FlowVisor. It spawns multiple pseudo
    Swich instances and Controller instances which wrap around
    the target FlowVisor. It also spawns an API client to
    exchange commands and responses with FlowVisor.
    No actual swiches or controllers are needed for the test.

    There are two parts to running the test framework:

    * Building the python libraries that support the OF protocol
    * Running 'fvt', the main entry point of the test framework

    Normally log output from fvt is sent to the file fvt.log, but
    can be redirected to the console by specifying --log-file="".

    The test framework currently supports version 1.0 of OpenFlow.

    FVTest is based on unittest which is included in the standard Python
    distribution.
    This version of testing Framework is exploiting OFTest
    testing framework for generating and parsing OpenFlow protocol
    messages and wrapping python unit test.

Quick Start
===========

    You need to have Python setup tools and Scapy installed on your
    system.  See 'Pre-requisites' below.
    Also make sure you have your FlowVisor installed.

      # cd (flowvisor-test directory)/tools/munger
      # make install
      # cd ../../tests
      # ./fvt --list    --- To see what tests are available
      Then you can run the tests with several conbinations of options
      such as:
      # ./fvt
      # ./fvt --verbose --log-file=""
      # ./fvt --test-spec=<mod>

Longer Start
============

    1.  Pre-requisites:
        * A FlowVisor to test, which supports OpenFlow 1.0
        * Root privilege on host running fvt
        * Python. The test has been verified with Python2.6
        * Python setup tools (e.g.: sudo apt-get install python-setuptools)
        * scapy installed:  http://www.secdev.org/projects/scapy/
          'sudo apt-get install scapy' should work on Debian.
        * tcpdump installed (optional, but scapy will complain if it's
          not there)
        * Doxygen and doxypy for document generation (optional)
        * lint for source checking (optional)

    2.  Build the OpenFlow Python message classes

        Important:  The OF version used by the controller is based on
        the file in tools/pylibopenflow/include/openflow.h
        This is currently the 1.0 release file.

        cd (flowvisor-test directory)/tools/munger
        make install

        This places files in (flowvisor-test directory)/src/python/oftest/src
        and then calls setuptools to install on the local host

    3.  Run fvt
        cd (flowvisor-test directory)/tests
        ./fvt
        To see options, run:
        ./fvt --help

Helpful Note: Rebuilding
========================

    If you ever make a change to the code in src/oftest/python...
    you must rebuild and reinstall the source code.  See Step (2)
    in the Longer Start above.

    If you see

        WARNING:..:Could not import file ...

    There is likely a Python error in the file.  Try invoking the
    Python cli directly and importing the file to get more
    information.

FVT Command Line Options
========================

    Here is a summary of the fvt command line options.  Use --help to see
    the long and short command option names.

    test_dir          : Directory to search for test files (default .)
    test_spec         : Specification of test(s) to run
    fv_cmd            : FlowVisor executable to test against
    log_file          : Filename for test logging
    list              : Boolean:  List all tests and exit
    debug             : String giving debug level (info, warning, error...)
    verbose           : Same as debug=verbose
    timeout           : Seconds before the test gives up receiving packet

Overview
========

    The directory structure is currently:

     <functiontest>
         `
         |-- doc
         |-- src
         |   `-- python
         |       `-- oftest
         |-- tests
         |   `-- fvt and files with test cases
         `-- tools
             |-- munger
             `-- pylibopenflow

    The tools directory is what processes the OpenFlow header
    files to produce Python classes representing OpenFlow messages.
    The results are placed in src/python/oftest and currently
    include:

        message.py:      The main API providing OF message classes
        error.py:        Subclasses for error messages
        action.py:       Subclasses for action specification
        cstruct.py:      Direct representation of C structures in Python
        class_maps.py:   Addition info about C structures

    In addition, the following Python files are present in
    src/python/oftest:

        fakedevice.py:   The controller and switch representations
        action_list.py:  Action list class

    Tests are run from the tests directory.  The file fvt is the
    top level entry point for tests.  Try ./fvt --help for some more.

Important Notes
===============

    1.  If you edit any of the files in src/python/oftest or any of the
    scripts in tools/munger/scripts, you MUST re-run make install.  This
    is easy to forget.

    2.  If you are running into issues with transactions, and it appears
    that OpenFlow messages aren't quite right, start by looking at any
    length fields in the packets.  With the local platform, you can use
    wireshark on the loopback interface.

Adding Your Own Test Cases
==========================

    You can:

        * Add cases to an existing file
        * Add a new file

    If you add cases to an existing file, each case should be its own
    class.  It must inherit from unittest.TestCase or one of its
    derivatives and define runTest (that's how test cases are discovered).

    If you add a new file, it must implement a top level function called
    test_set_init which takes a configuration dictionary.  See:
        templatetest.py
    for an example.
    Each test case in the new file must derive from unittest.TestCase.
    Inheriting from templatetest.py is highly recommended.

    CONVENTIONS:

    The first line of the doc string for a file and for a test class is
    displayed in the list command.  Please keep it clear and under 50
    characters.

Other Info
==========

    * Build doc with
      $ cd (flowvisor-test directory)/tools/munger
      $ make doc
    Places the results in (flowvisor-test directory)/doc/html
    If you have problems, check the install location doxypy.py and
    that it is set correctly in functiontest/doc/Doxyfile


