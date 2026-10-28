# sample-project

A tiny inventory module that Steward's samples work on. One test fails on purpose
(`discount_percent` is a percentage, but `order_total` treats it as a fraction).

Run the tests:

```
python -m unittest -v
```
