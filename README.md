"""
NSX Automation Code for CI/CD pipeline.

Run this as a Test to generate Results and failure for NSX Configuration.
The test creates a log file as well as a junit style result xml, that can be feed
in Jenkins for pipeline automation.

Record the changes done to each file at the begining of the program for quick reference as well as here.

Dependency:
pip install pytest
pip install pytest-dependency

The Data directory contains the config file, which is the place holder of all your variables.

A Dependent Test Can be Marked with @pytest.mark.dependency annotation.

For.eg:

@pytest.mark.dependency()
def test_Create_VXLAN():
    ...
    ...

@pytest.mark.dependency(depends=["test_Create_VXLAN"])
def test_Check_Prep_Status():
    ...
    ...

In the previous example, test_Check_Prep_Status() depends on the pass status of test_Create_VXLAN()


A Test can be skipped with @pytest.mark.skipif(config.SKIP_DEPLOY_EDGE,reason="LDU19 doesnot need Edge deployment") annotation.

For. e.g:
@pytest.mark.skipif(config.SKIP_DEPLOY_EDGE,reason="LDU19 doesnot need Edge deployment")
def test_Deploy_Edge():
    ...
    ...

If SKIP_DEPLOY_EDGE = True in the config file(Data directory) then the Test/Function would skip execution.

The skip happens when the statement/ variable is evaluated to true.

Make sure you do not skip any dependent function/ Tests.


Run:
Donot edit the main Test.py file. Create a Test File of your own and renale it as per your Project. 
For, e.g Test_LDU19.py
And then Run as:

pytest python -m pytest Test_LDU19.py -v -s --junitxml=nsxConfigTest.xml



version 1 :
Initial : Author : smrutim
Contributor: Haritej for VIB installation status.


"""