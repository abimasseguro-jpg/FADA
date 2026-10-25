"""FADA: adaptive scheduling primitives and policies."""

from .control import PolicyController
from .cpu_homologation import (
    CPU_HOMOLOGATION_KERNEL_VERSION,
    CpuCapability,
    CpuKernelResult,
    discover_cpu_capability,
    run_cpu_kernel,
)
from .calibration import (
    CALIBRATION_METRICS_SCHEMA_VERSION,
    CalibrationMetrics,
    DurationFeedback,
    calibrate_held_out,
)
from .concurrency import (
    CONCURRENCY_ESTIMATE_SCHEMA_VERSION,
    CONCURRENCY_SAMPLE_SCHEMA_VERSION,
    ConcurrencySample,
    ObservedConcurrencyCurve,
    ThroughputEstimate,
)
from .config import (
    RESOURCE_CONFIG_SCHEMA_VERSION,
    ResourceConfigError,
    load_machine_resource_config,
    machine_resource_config_from_dict,
)
from .domain import Decision, Task, WorkerSlot
from .estimation import ScenarioEstimator
from .estimation_v02 import (
    DURATION_ESTIMATE_SCHEMA_VERSION,
    ESTIMATOR_V02_VERSION,
    DurationEstimate,
    EstimatorContext,
    StratifiedDurationEstimator,
)
from .observations import (
    DURATION_OBSERVATION_SCHEMA_VERSION,
    DurationObservation,
    ExecutionOutcome,
)
from .policy import HybridPolicy
from .policy_estimator import PolicyEstimatorAdapter
from .policy_v02 import GuardedHybridPolicy
from .policy_v03 import PlanGuardedHybridPolicy
from .policy_v04 import BoundedPlanGuardedHybridPolicy
from .policy_cost_progress import CostWeightedProgressPolicy, ProgressSnapshot
from .policy_scenario_cohort import (
    ConcurrentScenarioPolicy,
    CostBalancedScenarioPolicy,
    ScenarioStatus,
    ScenarioWorkStatus,
)
from .resource_control import ResourceController
from .resource_domain import (
    CAPACITY_RECOMMENDATION_SCHEMA_VERSION,
    RESOURCE_TELEMETRY_SCHEMA_VERSION,
    CapacityAction,
    CapacityActuator,
    CapacityLevel,
    CapacityReceipt,
    CapacityRecommendation,
    MachineResourceConfig,
    NoOpCapacityActuator,
    ResourceMode,
    ResourceTelemetry,
)
from .resource_replay import (
    ResourceReplayRecord,
    ResourceReplaySummary,
    replay_resource_telemetry,
    summarize_resource_replay,
)
from .telemetry import (
    DECISION_LEDGER_SCHEMA_VERSION,
    DecisionLedgerEntry,
    append_entry,
    read_entries,
)

__all__ = [
    "CPU_HOMOLOGATION_KERNEL_VERSION",
    "CALIBRATION_METRICS_SCHEMA_VERSION",
    "CONCURRENCY_ESTIMATE_SCHEMA_VERSION",
    "CONCURRENCY_SAMPLE_SCHEMA_VERSION",
    "CalibrationMetrics",
    "Decision",
    "DURATION_OBSERVATION_SCHEMA_VERSION",
    "DURATION_ESTIMATE_SCHEMA_VERSION",
    "ESTIMATOR_V02_VERSION",
    "CAPACITY_RECOMMENDATION_SCHEMA_VERSION",
    "RESOURCE_CONFIG_SCHEMA_VERSION",
    "RESOURCE_TELEMETRY_SCHEMA_VERSION",
    "CapacityAction",
    "CapacityActuator",
    "CapacityLevel",
    "CapacityReceipt",
    "CapacityRecommendation",
    "CpuCapability",
    "CpuKernelResult",
    "ConcurrencySample",
    "DurationObservation",
    "DurationFeedback",
    "DurationEstimate",
    "EstimatorContext",
    "ExecutionOutcome",
    "HybridPolicy",
    "GuardedHybridPolicy",
    "PlanGuardedHybridPolicy",
    "BoundedPlanGuardedHybridPolicy",
    "CostWeightedProgressPolicy",
    "ConcurrentScenarioPolicy",
    "CostBalancedScenarioPolicy",
    "ScenarioStatus",
    "ScenarioWorkStatus",
    "ProgressSnapshot",
    "MachineResourceConfig",
    "NoOpCapacityActuator",
    "ObservedConcurrencyCurve",
    "PolicyController",
    "PolicyEstimatorAdapter",
    "ResourceController",
    "ResourceConfigError",
    "ResourceMode",
    "ResourceReplayRecord",
    "ResourceReplaySummary",
    "ResourceTelemetry",
    "ScenarioEstimator",
    "StratifiedDurationEstimator",
    "Task",
    "ThroughputEstimate",
    "WorkerSlot",
    "load_machine_resource_config",
    "discover_cpu_capability",
    "machine_resource_config_from_dict",
    "replay_resource_telemetry",
    "run_cpu_kernel",
    "summarize_resource_replay",
    "DECISION_LEDGER_SCHEMA_VERSION",
    "DecisionLedgerEntry",
    "append_entry",
    "calibrate_held_out",
    "read_entries",
]
__version__ = "0.1.0"
