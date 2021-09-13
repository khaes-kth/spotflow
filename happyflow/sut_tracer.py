import trace
import copy
from happyflow.utils import *
from happyflow.sut_model import SUTStateResult


class Trace2(trace.Trace):

    def __init__(self, count=1, trace=1, countfuncs=0, countcallers=0,
                 ignoremods=(), ignoredirs=(), infile=None, outfile=None,
                 timing=False, trace_collector=None):

        super().__init__(count, trace, countfuncs, countcallers, ignoremods, ignoredirs, infile, outfile, timing)
        self.trace_collector = trace_collector

    def globaltrace_lt(self, frame, why, arg):

        if why == 'call':
            code = frame.f_code

            self.trace_collector.collect_flow_and_state(frame, 'global', why)

            filename = frame.f_globals.get('__file__', None)
            if filename:
                # XXX _modname() doesn't work right for packages, so
                # the ignore support won't work right for packages
                modulename = trace._modname(filename)
                if modulename is not None:
                    ignore_it = self.ignore.names(filename, modulename)
                    if not ignore_it:
                        # if self.trace:
                        #     print((" --- modulename: %s, funcname: %s"
                        #            % (modulename, code.co_name)))
                        return self.localtrace
            else:
                return None

    def localtrace_trace_and_count(self, frame, why, arg):

        if why == "line" or why == 'return':

            # CHANGE
            self.trace_collector.collect_flow_and_state(frame, 'local', why)

            # record the file name and line number of every trace
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            key = filename, lineno
            self.counts[key] = self.counts.get(key, 0) + 1

            # if self.start_time:
            #     print('%.2f' % (_time() - self.start_time), end=' ')
            # bname = os.path.basename(filename)
            # print("%s(%d): %s" % (bname, lineno,
            #                       linecache.getline(filename, lineno)), end='')
        return self.localtrace


class TraceCollector:

    def __init__(self):
        self.test_name = None
        self.sut_full_name = None
        self.local_traces = {}
        # self.all_sut_states = {}

    def collect_flow_and_state(self, frame, data_type, why):

        entity_name = find_full_func_name(frame)

        if entity_name and self.sut_full_name and entity_name.startswith(self.sut_full_name):
            if entity_name not in self.local_traces:
                self.local_traces[entity_name] = []

            if data_type == 'global':
                sut_flows = self.local_traces[entity_name]
                state = SUTStateResult(entity_name)
                sut_flows.append((self.test_name, [], state))

            if data_type == 'local':
                sut_flows = self.local_traces[entity_name]
                # get the last flow and update it
                test_name, last_flow, last_state_result = sut_flows[-1]

                lineno = frame.f_lineno
                if why == 'line':
                    last_flow.append(lineno)

                if last_state_result:
                    argvalues = inspect.getargvalues(frame)
                    for argvalue in argvalues.locals:
                        value = copy.copy(argvalues.locals[argvalue])
                        last_state_result.add(name=argvalue, value=value, line=lineno)
