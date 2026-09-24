"""BASEERA AI analyst team.

A team of specialised agents that does the complete job of a senior data analyst on any
tabular dataset: understand the data, audit its quality, describe it, test hypotheses,
explain changes, find drivers and segments, detect anomalies, forecast, recommend actions
and write the report.

Two rules hold everywhere in this package:

* Numbers come from deterministic, reproducible tools (``toolkit``). A language model may
  plan, choose tools and write prose, but it never computes a published figure.
* Every figure a model writes is checked against the evidence the tools produced
  (``critic.verify_numbers``). Unverified figures are flagged, never silently published.
"""
