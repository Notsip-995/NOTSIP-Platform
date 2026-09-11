from __future__ import annotations
from statistics import fmean
import math

class PredictiveMaintenance:
    """Trend-based health forecasting; outputs predictions separately from measurements."""
    def evaluate(self, samples: list[dict], metric: str, *, warning_slope: float = 0.1, failure_threshold: float | None = None) -> dict:
        values=[]
        for row in samples:
            value=row.get(metric)
            if isinstance(value,(int,float)) and math.isfinite(float(value)): values.append(float(value))
        if not values:
            return {'status':'UNKNOWN','metric':metric,'prediction':None,'warning':'insufficient data'}
        baseline=fmean(values[:max(1,len(values)//3)])
        latest=values[-1]
        if len(values)<3 or latest==values[0]: slope=0.0
        else: slope=(latest-values[0])/(len(values)-1)
        state='NORMAL'
        if abs(slope)>=warning_slope: state='DEGRADATION'
        if failure_threshold is not None and slope>0 and latest>=failure_threshold: state='ANOMALY'
        eta=None
        if failure_threshold is not None and slope>0 and latest<failure_threshold:
            eta=(failure_threshold-latest)/slope if slope else None
            if eta is not None and eta<=10: state='PREDICTED_FAILURE'
        return {'status':'SUCCESS','metric':metric,'measurement':{'latest':latest,'baseline':baseline,'samples':len(values)},'trend':{'slope_per_sample':slope,'state':state},'prediction':{'is_prediction':True,'estimated_samples_to_threshold':eta,'threshold':failure_threshold} if failure_threshold is not None else {'is_prediction':True,'direction':'increasing' if slope>0 else 'decreasing' if slope<0 else 'stable'}}
