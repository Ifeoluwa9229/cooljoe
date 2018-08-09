"""The Kaplan-Meier non-parametric survival function estimator."""

import numpy as np
import scipy.stats as st

from .base import NonparametricSurvival
from .. import SurvivalData
from ..utils.validation import check_int


class KaplanMeier(NonparametricSurvival):
    """Non-parametric survival function estimator for right-censored data.

    The Kaplan-Meier estimator (Kaplan & Meier 1958) is also called the
    product-limit estimator. Much of this implementation is inspired by the R
    package ``survival`` (Therneau (2015)).

    For a quick introduction to the Kaplan-Meier estimator, see e.g. Section 4.2
    in Cox & Oakes (1984) or Section 1.4.1 in Kalbfleisch & Prentice (2002). For
    a more thorough treatment, see Chapter 4 in Klein & Moeschberger (2003).

    Properties
    ----------
    conf_type : str
        Type of confidence interval for the survival function estimate to
        report. Possible values:
            * "linear"
            * "log"
            * "log-log"
            * "logit"
            * "arcsin"
        Confidence intervals for a survival probability p=S(t) are computed
        using normal approximation confidence intervals for a strictly
        increasing differentiable transformation y=f(p) using the delta method:
        if se(p) is the standard error of p, then the standard error of f(p) is
        se(p)*f'(p). Consequently, a confidence interval for f(p) is
            [f(p) + z * se(p) * f'(p), f(p) - z * se(p) * f'(p)],
        where z is the (1-conf_level)/2-quantile of the standard normal
        distribution. If g(y) denotes the inverse of f, then a confidence
        interval for p is
            [g(f(p) + z * se(p) * f'(p)), g(f(p) - z * se(p) * f'(p))].
        These confidence intervals were proposed by Borgan & Liestøl (1990). We
        give a table of the supported transformations below.

            name        f(p)            f'(p)               g(y)
            ------------------------------------------------------------------
            "linear"    p               1                   y
            "log"       log(p)          1/p                 exp(y)
            "log-log"   -log(-log(p))   -1/(p*log(p))       exp(-exp(-y))
            "logit"     log(p/(1-p))    1/(p*(1-p))         exp(y)/(1+exp(y))
            "arcsin"    arcsin(sqrt(p)) 1/(2*sqrt(p*(1-p))) sin(y)**2

        Our implementation also shrinks the intervals to be between 0 and 1 if
        necessary.
    conf_level : float
        Confidence level of the confidence intervals.
    var_type : str
        Type of variance estimate for the survival function to compute.
        Possible values:
            * "greenwood"
                Use Greenwood's formula (Greenwood (1926)).
            * "aalen-johansen"
                Use the Poisson moment approximation to the binomial suggested
                by Aalen & Johansen (1978). This is less frequently used than
                Greenwood's formula, and the two methods are usually close to
                each other numerically. However, Klein (1991) recommends using
                Greenwood's formula because it is less biased and has comparable
                or lower mean squared error.
            * "bootstrap"
                Use the bootstrap (repeatedly sampling with replacement from the
                data and estimating the survival curve each time) to estimate
                the survival function variance (Efron (1981)).

    References
    ----------
        * E. L. Kaplan and P. Meier. "Nonparametric estimation from incomplete
          observations". Journal of the American Statistical Association, Volume
          53, Issue 282 (1958), pp. 457--481.
          DOI: https://doi.org/10.2307/2281868
        * Terry M. Therneau. A Package for Survival Analysis in S. version 2.38
          (2015). CRAN: https://CRAN.R-project.org/package=survival
        * D. R. Cox and D. Oakes. Analysis of Survival Data. Chapman & Hall,
          London (1984), pp. ix+201.
        * John D. Kalbfleisch and Ross L. Prentice. The Statistical Analysis of
          Failure Time Data. Second Edition. Wiley (2002) pp. xiv+439.
        * John P. Klein and Melvin L. Moeschberger. Survival Analysis.
          Techniques for Censored and Truncated Data. Second Edition.
          Springer-Verlag, New York (2003) pp. xvi+538.
          DOI: https://doi.org/10.1007/b97377
        * Ørnulf Borgan and Knut Liestøl. "A note on confidence intervals and
          bands for the survival function based on transformations."
          Scandinavian Journal of Statistics. Volume 17, Number 1 (1990),
          pp. 35--41. JSTOR: http://www.jstor.org/stable/4616153
        * M. Greenwood. "The natural duration of cancer". Reports on Public
          Health and Medical Subjects. Volume 33 (1926), pp. 1--26.
        * Odd O. Aalen and Søren Johansen. "An empirical transition matrix for
          non-homogeneous Markov chains based on censored observations."
          Scandinavian Journal of Statistics. Volume 5, Number 3 (1978),
          pp. 141--150. JSTOR: http://www.jstor.org/stable/4615704
        * John P. Klein. "Small sample moments of some estimators of the
          variance of the Kaplan-Meier and Nelson-Aalen estimators."
          Scandinavian Journal of Statistics. Volume 18, Number 4 (1991),
          pp. 333--40. JSTOR: http://www.jstor.org/stable/4616215.
        * Bradley Efron. "Censored data and the bootstrap." Journal of the
          American Statistical Association. Volume 76, Number 374 (1981),
          pp. 312--19. DOI: https://doi.org/10.2307/2287832.
    """
    model_type = "Kaplan-Meier estimator"

    _conf_types = ("arcsin", "linear", "log", "log-log", "logit")

    # Types of variance estimators
    _var_types = ("aalen-johansen", "bootstrap", "greenwood")
    _var_type: str

    # How to handle tied event times for the Aalen-Johansen variance estimator
    _tie_breaks = ("continuous", "discrete")
    _tie_break: str

    # Number of bootstrap samples to draw
    _n_boot: int

    @property
    def var_type(self):
        """Type of variance estimate for the survival function to compute."""
        return self._var_type

    @var_type.setter
    def var_type(self, var_type):
        """Set the type of variance estimate."""
        if var_type in self._var_types:
            self._var_type = var_type
        else:
            raise ValueError(f"Invalid value for 'var_type': {var_type}.")

    @property
    def tie_break(self):
        """How to handle tied event times for the Aalen-Johansen variance
        estimator.
        """
        return self._tie_break

    @tie_break.setter
    def tie_break(self, tie_break):
        """Set the tie-breaking scheme."""
        if tie_break in self._tie_breaks:
            self._tie_break = tie_break
        else:
            raise ValueError(f"Invalid value for 'tie_break': {tie_break}.")

    @property
    def n_boot(self):
        """Number of bootstrap samples to draw when ``var_type`` is "bootstrap".
        Not used for any other values of ``var_type``.
        """
        return self._n_boot

    @n_boot.setter
    def n_boot(self, n_boot):
        """Set the number of bootstrap samples to draw for bootstrap variance
        estimates.
        """
        self._n_boot = check_int(n_boot, minimum=1)

    def __init__(self, conf_type="log-log", conf_level=0.95,
                 var_type="greenwood", tie_break="discrete", n_boot=500,
                 random_state=None):
        """Initialize the Kaplan-Meier survival function estimator.

        Parameters
        ----------
        conf_type : str, optional (default: "log-log")
            Type of confidence interval for the survival function estimate to
            report. Accepted values:
                * "linear"
                * "log"
                * "log-log"
                * "logit"
                * "arcsin"
            See this class's docstring for details.
        conf_level : float, optional (default: 0.95)
            Confidence level of the confidence intervals.
        var_type : str, optional (default: "greenwood")
            Type of variance estimate for the survival function to compute.
            Accepted values:
                * "greenwood"
                * "aalen-johansen"
                * "bootstrap"
            See this class's docstring for details.
        tie_break : str, optional (default: "discrete")
            Specify how to handle tied event times when computing the
            Aalen-Johansen variance estimate (when ``var_type`` is
            "aalen-johansen"). Ignored for other values of ``var_type``.
            Accepted values:
                * "discrete"
                    Simultaneous events are genuine ties and not due to grouping
                    or rounding.
                * "continuous"
                    True event times almost surely don't coincide, and any
                    observed ties are due to grouping or rounding.
            This choice changes the definition of the Nelson-Aalen estimator
            increment, which consequently changes the definition of the
            Aalen-Johansen variance estimate. See Sections 3.1.3 and 3.2.2 in
            Aalen, Borgan, & Gjessing (2008).
        n_boot : int, optional (default: 500)
            Number of bootstrap samples to draw when estimating the survival
            function variance using the bootstrap (when ``var_type`` is
            "bootstrap"). Ignored for other values of ``var_type``.
        random_state : int or numpy.random.RandomState, optional (default: None)
            Random number generator (or a seed for one) used for sampling and
            for variance computations if ``var_type`` is "bootstrap".

        References
        ----------
            * Odd O. Aalen, Ørnulf Borgan, and Håkon K. Gjessing. Survival and
              Event History Analysis. A Process Point of View. Springer-Verlag,
              New York (2008) pp. xviii+540.
              DOI: https://doi.org/10.1007/978-0-387-68560-1
        """
        # Parameter validation is done in each parameter's setter method
        self.conf_type = conf_type
        self.conf_level = conf_level
        self.var_type = var_type
        self.tie_break = tie_break
        self.n_boot = n_boot
        self.random_state = random_state

    def fit(self, time, status=None, entry=None, group=None, df=None,
            min_time=0):
        """Fit the Kaplan-Meier estimator to survival data.

        Parameters
        ----------
        time : one-dimensional array-like or str
            The observed times. If the DataFrame parameter ``df`` is provided,
            this can be the name of a column in ``df`` from which to get the
            observed times.
        status : one-dimensional array-like or str, optional (default: None)
            Censoring indicators. 0 means a right-censored observation, 1 means
            a true failure/event. If not provided, it is assumed that there is
            no censoring.  If the DataFrame parameter ``df`` is provided,
            this can be the name of a column in ``df`` from which to get the
            censoring indicators.
        entry : one-dimensional array-like or str, optional (default: None)
            Entry/birth times of the observations (for left-truncated data). If
            not provided, the entry time for each observation is set to 0. If
            the DataFrame parameter ``df`` is provided, this can be the name of
            a column in ``df`` from which to get the entry times.
        group : one-dimensional array-like or string, optional (default: None)
            Group/stratum labels for each observation. If not provided, the
            entire sample is taken as a single group. If the DataFrame parameter
            ``df`` is provided, this can be the name of a column in ``df`` from
            which to get the group labels.
        df : pandas.DataFrame, optional (default: None)
            Optional DataFrame from which to extract the data. If this parameter
            is specified, then the parameters ``time``, ``status``, ``entry``,
            and ``group`` can be column names of this DataFrame.
        min_time : numeric
            The minimum observed time to consider part of the sample.
            Observations with later event or censoring times are ignored. For
            the Kaplan-Meier estimator, this means that estimated quantity is
            the conditional survival function given survival up to ``min_time``.

        Returns
        -------
        self : KaplanMeier
            This KaplanMeier instance.
        """
        if isinstance(time, SurvivalData):
            self._data = time
        else:
            self._data = SurvivalData(time=time, status=status, entry=entry,
                                      group=group, df=df, min_time=min_time)

        # Compute the Kaplan-Meier product-limit estimator and related
        # quantities at the distinct failure times within each group
        self.estimate_ = []
        self.estimate_var_ = []
        self.estimate_ci_lower_ = []
        self.estimate_ci_upper_ = []
        for i, group in enumerate(self._data.group_labels):
            # d = number of events at an event time, y = size of the risk set at
            # an event time
            d = self._data.events[group].n_events
            y = self._data.events[group].n_at_risk

            # Product-limit survival probability estimates
            self.estimate_.append(np.cumprod(1. - d / y))

            # In the following block, the variable ``sigma2`` is the variance
            # estimate divided by the square of the survival function
            # estimate. It arises again in our confidence interval computations
            # later.
            if self._var_type == "bootstrap":
                # Estimate the survival function variance using the bootstrap
                var = _km_var_boot(data=self._data, index=i,
                                   random_state=self._random_state,
                                   n_boot=self.n_boot)
                self.estimate_var_.append(var)
                with np.errstate(divide="ignore", invalid="ignore"):
                    sigma2 = self.estimate_var_[i] / (self.estimate_[i] ** 2)
            else:
                # Estimate the survival function variance using Greenwood's
                # formula or the Aalen-Johansen method
                if self._var_type == "greenwood":
                    # Greenwood's formula
                    with np.errstate(divide="ignore"):
                        sigma2 = np.cumsum(d / y / (y - d))
                elif self._var_type == "aalen-johansen":
                    # Aalen-Johansen estimate
                    if self._tie_break == "discrete":
                        sigma2 = np.cumsum(d / (y ** 2))
                    elif self._tie_break == "continuous":
                        # Increments of sum in equation (3.14) on page 84 of
                        # Aalen, Borgan, & Gjessing (2008)
                        inc = np.empty(len(d), dtype=np.float_)
                        for j in range(len(d)):
                            inc[j] = np.sum(1 / (y[j] - np.arange(d[j])) ** 2)
                        sigma2 = np.cumsum(inc)
                    else:
                        # This should not be reachable
                        raise RuntimeError(
                            f"Invalid tie-breaking scheme: {self._tie_break}.")
                else:
                    # This should not be reachable
                    raise RuntimeError(
                        f"Invalid variance type: {self._var_type}.")

                with np.errstate(invalid="ignore"):
                    self.estimate_var_.append((self.estimate_[i] ** 2) * sigma2)

            # Standard normal quantile for confidence intervals
            z = st.norm.ppf((1 - self.conf_level) / 2)

            # Compute confidence intervals at the observed event times
            if self._conf_type == "linear":
                # Normal approximation CI
                c = z * np.sqrt(self.estimate_var_[i])
                lower = self.estimate_[i] + c
                upper = self.estimate_[i] - c
            elif self._conf_type == "log":
                # CI based on a delta method CI for log(S(t))
                with np.errstate(invalid="ignore"):
                    c = z * np.sqrt(sigma2)
                    lower = self.estimate_[i] * np.exp(c)
                    upper = self.estimate_[i] * np.exp(-c)
            elif self._conf_type == "log-log":
                # CI based on a delta method CI for -log(-log(S(t)))
                with np.errstate(divide="ignore", invalid="ignore"):
                    c = z * np.sqrt(sigma2) / np.log(self.estimate_[i])
                    lower = self.estimate_[i] ** np.exp(c)
                    upper = self.estimate_[i] ** np.exp(-c)
            elif self._conf_type == "logit":
                # CI based on a delta method CI for log(S(t)/(1-S(t)))
                with np.errstate(invalid="ignore"):
                    odds = self.estimate_[i] / (1 - self.estimate_[i])
                    c = z * np.sqrt(sigma2) / (1 - self.estimate_[i])
                    lower = 1 - 1 / (1 + odds * np.exp(c))
                    upper = 1 - 1 / (1 + odds * np.exp(-c))
                pass
            elif self._conf_type == "arcsin":
                # CI based on a delta method CI for arcsin(sqrt(S(t))
                with np.errstate(invalid="ignore"):
                    arcsin = np.arcsin(np.sqrt(self.estimate_[i]))
                    odds = self.estimate_[i] / (1 - self.estimate_[i])
                    c = 0.5 * z * np.sqrt(odds * sigma2)
                    lower = np.sin(np.maximum(0., arcsin + c)) ** 2
                    upper = np.sin(np.minimum(np.pi / 2, arcsin - c)) ** 2
            else:
                # This should not be reachable
                raise RuntimeError(
                    f"Invalid confidence interval type: {self._conf_type}.")

            # Force confidence interval bounds to be between 0 and 1
            with np.errstate(invalid="ignore"):
                self.estimate_ci_lower_.append(np.maximum(lower, 0.))
                self.estimate_ci_upper_.append(np.minimum(upper, 1.))

            # Make sure that variance estimates and confidence intervals are NaN
            # when the estimated survival probability is zero
            ind_zero = (self.estimate_[i] == 0.)
            self.estimate_var_[i][ind_zero] = np.nan
            self.estimate_ci_lower_[i][ind_zero] = np.nan
            self.estimate_ci_upper_[i][ind_zero] = np.nan

        self.fitted = True
        return self


def _km_var_boot(data: SurvivalData, index, random_state, n_boot):
    """Estimate Kaplan-Meier survival function variance using the bootstrap.

    Parameters
    ----------
    data : SurvivalData
        Survival data used to fit the Kaplan-Meier estimator.
    index : int
        The group index.
    random_state : numpy.random.RandomState
        Random number generator.
    n_boot : int
        Number of bootstrap samples to draw.

    Returns
    -------
    survival_var : numpy.ndarray
        One-dimensional array of survival function variance estimates at each
        observed event time.
    """
    # Extract observed times, censoring indicators, and entry times for the
    # specified group
    ind = (data.group == data.group_labels[index])
    time = np.asarray(data.time[ind])
    status = np.asarray(data.status[ind])
    entry = np.asarray(data.entry[ind])

    # Distinct true event times
    events = np.unique(time[status == 1])

    # n = sample size, k = number of distinct true events
    n = len(time)
    k = len(events)

    # Initialize array of bootstrap Kaplan-Meier survival function estimates at
    # the observed true event times
    survival_boot = np.empty(shape=(n_boot, k), dtype=np.float_)

    # The bootstrap
    for i in range(n_boot):
        # Draw a bootstrap sample
        ind_boot = random_state.choice(n, size=n, replace=True)
        time_boot = time[ind_boot]
        status_boot = status[ind_boot]
        entry_boot = entry[ind_boot]

        # e = number of events at an event time, r = size of the risk set at an
        # event time
        e = np.empty(shape=(k,), dtype=np.int_)
        r = np.empty(shape=(k,), dtype=np.int_)
        for j, t in enumerate(events):
            e[j] = np.sum((time_boot == t) & (status_boot == 1))
            r[j] = np.sum((entry_boot <= t) & (time_boot >= t))

        # Compute the survival curve
        with np.errstate(divide="ignore", invalid="ignore"):
            survival_boot[i] = np.cumprod(1. - e / r)

        # Special case: if sufficiently late times didn't make it into our
        # bootstrap sample, then the risk set at those time is empty and the
        # resulting survival function estimates are nan (not a number). Instead,
        # make the survival probability at these times zero.
        survival_boot[i, r == 0] = 0.

    return survival_boot.var(axis=0, ddof=1)