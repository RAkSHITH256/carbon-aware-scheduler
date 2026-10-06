# MLOps-Driven Predictive Carbon-Aware Cloud Scheduling

An intelligent cloud scheduling system that uses **Machine Learning, MLOps, and multi-objective optimization** to reduce cloud carbon emissions while satisfying cost, resource, and SLA constraints.

## 🎯 Objectives

- 🌱 Reduce CO₂e emissions
- 💰 Optimize cloud cost
- ⏱️ Meet workload deadlines/SLA
- 🖥️ Consider CPU, memory, and GPU requirements
- 🤖 Predict future carbon intensity
- ☁️ Schedule workloads across regions and time

## 🏗️ Architecture

```text
Workload
   ↓
Workload Classification
   ↓
Carbon Intensity Prediction
   ↓
Multi-Objective Optimizer
   ↓
WHEN + WHERE + HOW
   ↓
Kubernetes
   ↓
Monitoring
   ↓
Actual Energy & CO₂e
   ↓
MLOps / Retraining
