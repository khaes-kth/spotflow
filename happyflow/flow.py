from happyflow.utils import obj_value
from happyflow.info import *


class TracedSystem:

    def __init__(self):
        self.traced_methods = {}

    def compute_flows(self):
        for traced_method in self.traced_methods.values():
            traced_method._compute_flows()

    def filter(self, filter_func):
        self.traced_methods = {k: v for k, v in self.traced_methods.items() if filter_func(k, v)}
        return self

    def has_calls(self, method_name, traced_method):
        return traced_method.calls

    def __getitem__(self, key):
        return self.traced_methods[key]

    def __setitem__(self, key, value):
        self.traced_methods[key] = value

    def __contains__(self, key):
        return key in self.traced_methods

    def __len__(self):
        return len(self.traced_methods)

    def __repr__(self):
        return repr(self.traced_methods)

    def __iter__(self):
        return iter(self.traced_methods.values())


class CallContainer:

    def __init__(self, calls):
        self.calls = calls

    def distinct_run_lines(self):
        lines = []
        for call in self.calls:
            lines.append(tuple(call.distinct_run_lines()))
        return lines

    def arg_states(self):
        args_and_values = {}
        for call in self.calls:
            if call.call_state and call.call_state.arg_states:
                for arg in call.call_state.arg_states:
                    if arg.name != 'self':
                        value = arg.value
                        args_and_values[arg.name] = args_and_values.get(arg.name, [])
                        args_and_values[arg.name].append(value)
        return args_and_values

    def yield_states(self):
        values = []
        for call in self.calls:
            if call.call_state:
                for yield_state in call.call_state.yield_states:
                    values.append(yield_state.value)
        return values

    def return_states(self):
        values = []
        for call in self.calls:
            if call.call_state and call.call_state.has_return():
                value = call.call_state.return_state.value
                values.append(value)
        return values

    def exception_states(self):
        values = []
        for call in self.calls:
            if call.call_state and call.call_state.has_exception():
                value = call.call_state.exception_state.value
                values.append(value)
        return values

    def call_stack(self):
        cs = []
        for call in self.calls:
            cs.append(call.call_stack)
        return cs

    def callers(self):
        return sorted(set(map(lambda each: each[-2], self.call_stack())))

    def tests(self):
        return sorted(set(map(lambda each: each[0], self.call_stack())))

    def _select_calls_by_lines(self, distinct_lines):
        calls = []
        for call in self.calls:
            if tuple(call.distinct_run_lines()) == tuple(distinct_lines):
                calls.append(call)
        return calls


class TracedMethod(CallContainer):

    def __init__(self, method_info):
        super().__init__(calls=[])
        self.info = method_info
        self.method_name = method_info.name
        self.flows = []
        self._calls = {}

    def _add_call(self, run_lines, call_state, call_stack, call_id):
        call = MethodCall(run_lines, call_state, call_stack, self)
        self.calls.append(call)
        self._calls[call_id] = call
        return call

    def _add_flow(self, flow_pos, distinct_run_lines, flow_calls):
        flow = MethodFlow(flow_pos, distinct_run_lines, flow_calls, self)
        self.flows.append(flow)
        return flow

    def _compute_flows(self):
        most_common_run_lines = Analysis(self).most_common_run_lines()
        flow_pos = 0
        for run_lines in most_common_run_lines:
            flow_pos += 1
            distinct_run_lines = run_lines[0]

            flow_calls = self._select_calls_by_lines(distinct_run_lines)
            flow = self._add_flow(flow_pos, distinct_run_lines, flow_calls)
            flow._update_flow_info()

        self.info._update_trace_data(self)

    def _get_call_from_id(self, call_id):
        return self._calls.get(call_id, None)


class MethodFlow(CallContainer):

    def __init__(self, pos, distinct_run_lines, calls, traced_method):
        super().__init__(calls)
        self.pos = pos
        self.distinct_run_lines = distinct_run_lines
        self.traced_method = traced_method
        self.info = None
        self._found_first_run_line = False

    def _update_flow_info(self):
        lineno = 0
        self.info = FlowInfo(self, len(self.traced_method.calls))
        self._found_first_run_line = False

        for lineno_entity in range(self.traced_method.info.start_line, self.traced_method.info.end_line+1):
            lineno += 1

            line_status = self._get_line_status(lineno_entity)
            line_state = self._get_line_state(lineno_entity)
            line_info = LineInfo(lineno, lineno_entity, line_status, line_state, self.traced_method.info)

            self.info.append(line_info)
            self.info.update_run_status(line_info)

    def _get_line_status(self, current_line):

        if current_line in self.distinct_run_lines:
            self._found_first_run_line = True
            return RunStatus.RUN

        # _find_executable_linenos of trace returns method/function definitions as executable lines (?).
        # We should flag those definitions as not executable lines (NOT_EXEC). Otherwise, the definitions
        # would impact on the flows. The solution for now is flagging all first lines as not executable
        # until we find the first run line. This way, the definitions are flagged as not executable lines...
        if not self._found_first_run_line:
            return RunStatus.NOT_EXEC

        if current_line not in self.distinct_run_lines:
            if not self.traced_method.info.line_is_executable(current_line):
                return RunStatus.NOT_EXEC

        return RunStatus.NOT_RUN

    def _get_line_state(self, current_line, n=0):
        call = self.calls[n]
        return call.get_line_state(current_line)


class MethodCall:

    def __init__(self, run_lines, call_state, call_stack, traced_method):
        self.run_lines = run_lines
        self.call_state = call_state
        self.call_stack = call_stack
        self.traced_method = traced_method

    def __eq__(self, other):
        return other == self.run_lines

    def distinct_run_lines(self):
        return sorted(list(set(self.run_lines)))

    def get_line_state(self, lineno):

        if self.traced_method.info.start_line == lineno:
            return self.line_arg_state()

        if lineno in self.traced_method.info.return_lines:
            return self.line_return_state()

        states = self.call_state.states_for_line(lineno)
        if states:
            return self.line_var_states(states)

        return ''

    def line_arg_state(self):
        arg_str = ''
        for arg in self.call_state.arg_states:
            if arg.name != 'self':
                arg_str += str(arg)
        return StateStatus.ARG, arg_str

    def line_return_state(self):
        return_state = self.call_state.return_state
        return StateStatus.RETURN, str(return_state)

    def line_var_states(self, states):
        return StateStatus.VAR, states


class CallState:

    def __init__(self):
        self.var_states = {}
        self.arg_states = []
        self.yield_states = []
        self.return_state = None
        self.exception_state = None

    def states_for_line(self, lineno):
        states = []
        for var in self.var_states:
            var_states = ''
            if var != 'self':
                call_state = self.var_states[var]
                for state in call_state.states:
                    if state.inline == lineno:
                        if str(state) not in var_states and state.value_has_changed:
                            var_states += str(state) + ' '
            if var_states:
                states.append(var_states.strip())
        return states

    def get_yield_states(self):
        if len(self.yield_states) <= 1:
            return self.yield_states
        # Remove the last element. This one is saved as an implicit return
        return self.yield_states[:-1]

    def has_return(self):
        return self.return_state is not None

    def has_exception(self):
        return self.exception_state is not None

    def has_yield(self):
        return len(self.yield_states) > 0

    def _save_arg_states(self, argvalues, lineno):
        for arg in argvalues.args:
            value = obj_value(argvalues.locals[arg])
            arg_state = ArgState(arg, value, lineno)
            self.arg_states.append(arg_state)

        if argvalues.varargs:
            value = obj_value(argvalues.locals[argvalues.varargs])
            arg_state = ArgState(argvalues.varargs, value, lineno)
            self.arg_states.append(arg_state)

        if argvalues.keywords:
            value = obj_value(argvalues.locals[argvalues.keywords])
            arg_state = ArgState(argvalues.keywords, value, lineno)
            self.arg_states.append(arg_state)

    def _save_var_states(self, argvalues, lineno, inline):
        for arg in argvalues.locals:
            value = obj_value(argvalues.locals[arg])
            self._save_var_state(name=arg, value=value, lineno=lineno, inline=inline)

    def _save_var_state(self, name, value, lineno, inline):
        self.var_states[name] = self.var_states.get(name, VarStateHistory(name, []))
        self.var_states[name].add_var_state(name, value, lineno, inline)

    def _save_yield_state(self, value, lineno):
        self.yield_states.append(YieldState(value, lineno))

    def _save_return_state(self, value, lineno):
        self.return_state = ReturnState(value, lineno)

    def _save_exception_state(self, value, lineno):
        self.exception_state = ExceptionState(value, lineno)


class VarStateHistory:

    def __init__(self, name, states):
        self.name = name
        self.states = states

    def add_var_state(self, name, value, lineno, inline):
        value_has_changed = self.detect_value_has_changed(value)
        new_state = VarState(name, value, lineno, inline, value_has_changed)
        self.states.append(new_state)

    def detect_value_has_changed(self, new_value):
        if not self.states:
            return True
        last_state = self.get_last_state()
        try:
            if last_state.value != new_value:
                return True
            return False
        except Exception as e:
            return False

    def get_last_state(self):
        return self.states[-1]

    def first_last(self):
        if len(self.states) == 1:
            return self.states[0], self.states[0]
        return self.states[0], self.states[-1]

    def distinct_values(self):
        values = {}
        for state in self.states:
            if state.value not in values:
                values[state.value] = None
        return values.keys()

    def distinct_sequential_values(self):
        values = []
        b = None
        for state in self.states:
            if state.value != b:
                values.append(state.value)
            b = state.value
        return values

    def __str__(self):
        return f'name: {self.name}, values: {len(self.states)}'


class VarState:

    def __init__(self, name, value, lineno, inline, value_has_changed=False):
        self.name = name
        self.value = value
        self.lineno = lineno
        self.inline = inline
        self.value_has_changed = value_has_changed

    def __str__(self):
        return f'{self.name}={self.value}'


class ArgState:

    def __init__(self, name, value, lineno):
        self.name = name
        self.value = value
        self.lineno = lineno

    def __str__(self):
        return f'{self.name}={self.value}'


class ReturnState:

    def __init__(self, value, lineno=0):
        self.value = value
        self.lineno = lineno

    def __str__(self):
        return f'{self.value}'

    def __eq__(self, other):
        return self.value == other


class YieldState:

    def __init__(self, value, lineno=0):
        self.value = value
        self.lineno = lineno

    def __str__(self):
        return f'{self.value}'

    def __eq__(self, other):
        return self.value == other


class ExceptionState:

    def __init__(self, value, line=0):
        self.value = value
        self.line = line

    def __str__(self):
        return f'{self.value}'

    def __eq__(self, other):
        return self.value == other
