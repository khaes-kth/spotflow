from happyflow.report import Report
from happyflow.collector import Collector
from happyflow.unittest_utils import loadTestsFromModule, suite_runner


class HappyFlow:

    def __init__(self):
        self.collector = Collector()

    def target_methods(self, method_names):
        self.collector.method_names = method_names

    def target_files(self, file_names):
        self.collector.file_names = file_names

    def ignore_files(self, ignore_files):
        self.collector.ignore_files = ignore_files

    def collect_states(self, arg_states=True, return_states=True, yield_states=True,
                       exception_states=True, var_states=True):

        self.collector.collect_arg_states = arg_states
        self.collector.collect_return_states = return_states
        self.collector.collect_yield_states = yield_states
        self.collector.collect_exception_states = exception_states
        self.collector.collect_var_states = var_states

    def start(self):
        self.collector.start()

    def stop(self):
        self.collector.stop()

    def result(self):
        return self.collector.monitored_system

    def html_report(self, directory=None):
        # try:
        Report(self.collector.monitored_system).html_report(directory)
        # except Exception as e:
        #     print(e)

    def csv_report(self, directory=None):
        # try:
        Report(self.collector.monitored_system).csv_report(directory)
        # except Exception as e:
        #     print(e)

    def txt_report(self):
        try:
            Report(self.collector.monitored_system).txt_report()
            return True
        except Exception as e:
            print(e)
            return False


def live(func, target_methods):
    hp = HappyFlow()
    hp.target_methods(target_methods)

    hp.start()
    func()
    hp.stop()

    hp.txt_report()


def monitor(func, target_methods=None, target_files=None, ignore_files=None,
            arg_states=True, return_states=True, yield_states=True, exception_states=True, var_states=True):
    hp = HappyFlow()
    hp.target_methods(target_methods)
    hp.target_files(target_files)
    hp.ignore_files(ignore_files)
    hp.collect_states(arg_states, return_states, yield_states, exception_states, var_states)

    hp.start()
    func()
    hp.stop()

    return hp.result()


def monitor_unittest_module(module, target_methods=None, target_files=None, ignore_files=None,
            arg_states=True, return_states=True, yield_states=True, exception_states=True, var_states=True):

    suite = loadTestsFromModule(module)
    suite = suite_runner(suite)

    return monitor(suite, target_methods, target_files, ignore_files,
                   arg_states, return_states, yield_states, exception_states, var_states)


