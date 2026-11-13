"""Streamlit demo for RuminantEval — wide ruminant evaluation + trial analysis."""
import streamlit as st
import pandas as pd

from src.ruminant_eval.evaluator import evaluate_csv
from src.ruminant_eval.factorial_anova import run_balanced_two_way_anova
from src.ruminant_eval.trial import trial_summary

st.title("RuminantEval — AI evaluation for ruminants")
st.write(
    "Scores AI answers about cattle, sheep and goats against golden "
    "references, flags dangerous advice, and analyses synthetic feed trials. "
    "All data in this demo is synthetic."
)

st.header("1. Evaluation")
results = evaluate_csv("data/eval_dataset.csv")
st.write(
    f"{results['question_id'].nunique()} questions, "
    f"{len(results)} answers. "
    f"Mean score: **{results['score'].mean():.1f} / 100**"
)
st.bar_chart(results.groupby("model")["score"].mean())
st.write("Error-type breakdown:")
st.write(results["error"].value_counts())
st.dataframe(results)

st.header("2. Trial 1 — One-way ANOVA (synthetic WAD goat trial, N=24)")
try:
    trial = pd.read_csv("data/trial_data.csv")
    summary = trial_summary(trial)
    st.write(f"ANOVA: F = {summary['anova_f']}, p = {summary['anova_p']}, significant = {summary['significant']}")
    st.write(f"Best treatment by mean daily gain: **{summary['best_treatment_by_mean_gain']}**")
    st.dataframe(trial.groupby("treatment")["daily_gain_g"].mean())
except FileNotFoundError:
    st.write("No trial data yet — run the trial generator in the README.")

st.header("3. Trial 2 — Two-way factorial ANOVA (synthetic dairy trial, N=32)")
st.write(
    "32 lactating Holsteins, 8 per cell. Factor A: concentrate level "
    "(Low_40 vs High_65 % DM). Factor B: rumen buffer / live yeast "
    "(Control vs Buffer_Yeast)."
)
try:
    dairy = pd.read_csv("data/trial_dairy_2x2.csv")
    for response in ("rumen_ph", "milk_yield_kg", "milk_fat_pct"):
        result = run_balanced_two_way_anova(dairy, response=response)
        st.subheader(response)
        st.write("Cell means (Mean ± SEM):")
        st.dataframe(result.cell_summary)
        table = pd.DataFrame(
            [
                {
                    "Source": row.source,
                    "SS": round(row.ss, 3),
                    "df": row.df,
                    "MS": round(row.ms, 3),
                    "F": round(row.f_stat, 2) if row.f_stat is not None else None,
                    "p": round(row.p_value, 4) if row.p_value is not None else None,
                }
                for row in result.table
            ]
        )
        st.dataframe(table)
except FileNotFoundError:
    st.write("No dairy trial data yet.")
