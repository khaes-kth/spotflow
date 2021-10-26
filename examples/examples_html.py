from happyflow.tracer import TraceRunner
from happyflow.target_loader import TargetEntityLoader
from happyflow.html_report import HTMLReport


def parseparam(s):
    s = ';' + str(s)
    plist = []
    while s[:1] == ';':
        s = s[1:]
        end = s.find(';')
        while end > 0 and (s.count('"', 0, end) - s.count('\\"', 0, end)) % 2:
            end = s.find(';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        if '=' in f:
            i = f.index('=')
            f = f[:i].strip().lower() + '=' + f[i+1:].strip()
        plist.append(f.strip())
        s = s[end:]
    return plist


def inputs_parseparam():
    # parseparam('a')
    parseparam('a=1;b=2')
    # parseparam('a="1;1"')


target = TargetEntityLoader.load_func(parseparam)
trace_result = TraceRunner.trace_from_func(inputs_parseparam, target)
flow_results = target.local_flows(trace_result)

for flow_result in flow_results:
    reporter = HTMLReport(flow_result.target_entity, flow_result)
    reporter.report(0)

