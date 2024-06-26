# Copyright (c) 2022-2024, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import math
from dataclasses import MISSING

# import torch

import omni.isaac.lab.sim as sim_utils
from omni.isaac.lab.assets import ArticulationCfg, AssetBaseCfg
from omni.isaac.lab.envs import ManagerBasedRLEnvCfg
from omni.isaac.lab.managers import CurriculumTermCfg as CurrTerm
from omni.isaac.lab.managers import EventTermCfg as EventTerm
from omni.isaac.lab.managers import ObservationGroupCfg as ObsGroup
from omni.isaac.lab.managers import ObservationTermCfg as ObsTerm
from omni.isaac.lab.managers import RewardTermCfg as RewTerm
from omni.isaac.lab.managers import SceneEntityCfg
from omni.isaac.lab.managers import TerminationTermCfg as DoneTerm
from omni.isaac.lab.scene import InteractiveSceneCfg
from omni.isaac.lab.sensors import ContactSensorCfg, RayCasterCfg, patterns
from omni.isaac.lab.terrains import TerrainImporterCfg
from omni.isaac.lab.utils import configclass
from omni.isaac.lab.utils.noise import AdditiveUniformNoiseCfg as Unoise
from omni.isaac.lab.utils.noise import GaussianNoiseCfg as Gnoise

# import omni.isaac.orbit_tasks.locomotion.velocity.mdp as mdp
import lab.flamingo.tasks.manager_based.locomotion.velocity.mdp as mdp

##
# Pre-defined configs
##
from omni.isaac.lab.terrains.config.rough import ROUGH_TERRAINS_CFG  # isort: skip


##
# Scene definition
##


@configclass
class MySceneCfg(InteractiveSceneCfg):
    """Configuration for the terrain scene with a legged robot."""

    # ground terrain
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=ROUGH_TERRAINS_CFG,
        max_init_terrain_level=5,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path="{NVIDIA_NUCLEUS_DIR}/Materials/Base/Architecture/Shingles_01.mdl",
            project_uvw=True,
        ),
        debug_vis=False,
    )
    # robots
    robot: ArticulationCfg = MISSING
    # sensors
    height_scanner = RayCasterCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base_link",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
        attach_yaw_only=True,
        pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=[1.6, 1.0]),
        debug_vis=False,
        mesh_prim_paths=["/World/ground"],
    )
    contact_forces = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/Robot/.*", history_length=3, track_air_time=True)
    # lights
    light = AssetBaseCfg(
        prim_path="/World/light",
        spawn=sim_utils.DistantLightCfg(color=(0.75, 0.75, 0.75), intensity=3000.0),
    )
    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(color=(0.13, 0.13, 0.13), intensity=1000.0),
    )


##
# MDP settings
##


@configclass
class CommandsCfg:
    """Command specifications for the MDP."""

    base_velocity = mdp.UniformVelocityCommandCfg(
        asset_name="robot",
        resampling_time_range=(10.0, 10.0),
        rel_standing_envs=0.02,
        rel_heading_envs=1.0,
        heading_command=True,
        heading_control_stiffness=0.5,
        debug_vis=True,
        ranges=mdp.UniformVelocityCommandCfg.Ranges(
            lin_vel_x=(-1.0, 1.0), lin_vel_y=(-1.0, 1.0), ang_vel_z=(-1.0, 1.0), heading=(-math.pi, math.pi)
        ),
    )


@configclass
class ActionsCfg:
    """Action specifications for the MDP."""

    joint_pos = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*_hip_joint", ".*_shoulder_joint", ".*_leg_joint"],
        scale=2.0,
        use_default_offset=True,
    )
    wheel_vel = mdp.JointVelocityActionCfg(
        asset_name="robot", joint_names=[".*_wheel_joint"], scale=25.0, use_default_offset=True
    )
    # joint_effort = mdp.JointEffortActionCfg(
    #     asset_name="robot",
    #     joint_names=[".*"],
    #     scale={
    #         ".*_hip_.*": 15.0,
    #         ".*_shoulder_.*": 15.0,
    #         ".*_leg_.*": 15.0,
    #         ".*_wheel_.*": 4.0,
    #     },
    # )


@configclass
class ObservationsCfg:
    """Observation specifications for the MDP."""

    @configclass
    class PolicyCfg(ObsGroup):
        """Observations for policy group."""

        # observation terms (order preserved)

        """
        Stack 0
        """

        joint_pos = ObsTerm(
            func=mdp.joint_pos_rel,
            noise=Unoise(n_min=-0.02, n_max=0.02),
            clip=(-25.0, 25.0),
            params={
                "asset_cfg": SceneEntityCfg("robot", joint_names=[".*_hip_joint", ".*_shoulder_joint", ".*_leg_joint"])
            },
        )

        # wheel_sin_pos = ObsTerm(
        #     func=mdp.joint_pos_rel_sin,
        #     noise=Unoise(n_min=-0.01, n_max=0.01),
        #     params={"asset_cfg": SceneEntityCfg("robot", joint_names=[".*_wheel_joint"])},
        # )
        # wheel_cos_pos = ObsTerm(
        #     func=mdp.joint_pos_rel_cos,
        #     noise=Unoise(n_min=-0.01, n_max=0.01),
        #     params={"asset_cfg": SceneEntityCfg("robot", joint_names=[".*_wheel_joint"])},
        # )
        joint_vel = ObsTerm(func=mdp.joint_vel_rel, noise=Unoise(n_min=-1.0, n_max=1.0), clip=(-25.0, 25.0))
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel, noise=Unoise(n_min=-0.1, n_max=0.1), clip=(-25.0, 25.0))
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, noise=Unoise(n_min=-0.2, n_max=0.2), clip=(-25.0, 25.0))
        base_euler = ObsTerm(func=mdp.root_euler_angle, noise=Unoise(n_min=-0.15, n_max=0.15), clip=(-25.0, 25.0))
        actions = ObsTerm(func=mdp.last_action, noise=Unoise(n_min=-0.05, n_max=0.05), clip=(-25.0, 25.0))

        """
        Stack 1
        """

        prev_joint_pos = ObsTerm(func=mdp.prev_joint_pos_rel)
        # prev_wheel_sin_pos = ObsTerm(func=mdp.prev_joint_pos_rel_sin)
        # prev_wheel_cos_pos = ObsTerm(func=mdp.prev_joint_pos_rel_cos)
        prev_joint_vel = ObsTerm(func=mdp.prev_joint_vel_rel)
        prev_base_lin_vel = ObsTerm(func=mdp.prev_base_lin_vel)
        prev_base_ang_vel = ObsTerm(func=mdp.prev_base_ang_vel)
        prev_base_euler = ObsTerm(func=mdp.prev_root_euler_angle)
        prev_actions = ObsTerm(func=mdp.prev_last_action)

        """
        Stack 2
        """

        prev2_joint_pos = ObsTerm(func=mdp.prev_prev_joint_pos_rel)
        # prev2_wheel_sin_pos = ObsTerm(func=mdp.prev_prev_joint_pos_rel_sin)
        # prev2_wheel_cos_pos = ObsTerm(func=mdp.prev_prev_joint_pos_rel_cos)
        prev2_joint_vel = ObsTerm(func=mdp.prev_prev_joint_vel_rel)
        prev2_base_lin_vel = ObsTerm(func=mdp.prev_prev_base_lin_vel)
        prev2_base_ang_vel = ObsTerm(func=mdp.prev_prev_base_ang_vel)
        prev2_base_euler = ObsTerm(func=mdp.prev_prev_root_euler_angle)
        prev2_actions = ObsTerm(func=mdp.prev_prev_last_action)

        velocity_commands = ObsTerm(func=mdp.generated_commands, params={"command_name": "base_velocity"})

        def __post_init__(self):
            self.enable_corruption = True
            self.concatenate_terms = True

            # if self.enable_corruption:
            #     self.actions = ObsTerm(func=mdp.delayed_last_action, noise=Unoise(n_min=-0.01, n_max=0.01))
            # else:
            #     self.actions = ObsTerm(func=mdp.last_action, noise=Unoise(n_min=-0.01, n_max=0.01))

    # observation groups
    policy: PolicyCfg = PolicyCfg()


@configclass
class EventCfg:
    """Configuration for events."""

    # startup
    physics_material = EventTerm(
        func=mdp.randomize_rigid_body_material,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "static_friction_range": (0.8, 1.2),
            "dynamic_friction_range": (1.0, 1.0),
            "restitution_range": (0.0, 0.0),
            "num_buckets": 64,
        },
    )
    robot_joint_stiffness_and_damping = EventTerm(
        func=mdp.randomize_actuator_gains,
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=[".*_hip_joint", ".*_shoulder_joint", ".*_leg_joint"]),
            "stiffness_distribution_params": (0.75, 1.5),
            "damping_distribution_params": (0.5, 2.0),
            "operation": "scale",
            "distribution": "log_uniform",
        },
    )
    robot_wheel_stiffness_and_damping = EventTerm(
        func=mdp.randomize_actuator_gains,
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=".*_wheel_joint"),
            "stiffness_distribution_params": (1.0, 1.0),
            "damping_distribution_params": (0.3, 3.0),
            "operation": "scale",
            "distribution": "log_uniform",
        },
    )
    robot_joint_friction_and_armature = EventTerm(
        func=mdp.randomize_joint_parameters,
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=[".*_hip_joint", ".*_shoulder_joint", ".*_leg_joint"]),
            "friction_distribution_params": (1.0, 1.0),
            "armature_distribution_params": (0.3, 3.0),
            "operation": "scale",
            "distribution": "uniform",
        },
    )
    robot_wheel_friction_and_armature = EventTerm(
        func=mdp.randomize_joint_parameters,
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=".*_wheel_joint"),
            "friction_distribution_params": (1.0, 1.0),
            "armature_distribution_params": (0.3, 3.0),
            "operation": "scale",
            "distribution": "uniform",
        },
    )
    add_base_mass = EventTerm(
        func=mdp.add_body_mass,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_link"),
            "mass_distribution_params": (-2.0, 2.0),
        },
    )

    # reset
    base_external_force_torque = EventTerm(
        func=mdp.apply_external_force_torque,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base"),
            "force_range": (0.0, 0.0),
            "torque_range": (-0.0, 0.0),
        },
    )

    reset_base = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)},
            "velocity_range": {
                "x": (-0.5, 0.5),
                "y": (-0.5, 0.5),
                "z": (-0.5, 0.5),
                "roll": (-0.5, 0.5),
                "pitch": (-0.5, 0.5),
                "yaw": (-0.5, 0.5),
            },
        },
    )

    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "position_range": (-0.0, 0.0),
            "velocity_range": (0.0, 0.0),
        },
    )

    # reset_robot_joints = EventTerm(
    #     func=mdp.reset_joints_by_scale,
    #     mode="reset",
    #     params={
    #         "position_range": (0.5, 1.5),
    #         "velocity_range": (0.0, 0.0),
    #     },
    # )

    # interval
    push_robot = EventTerm(
        func=mdp.push_by_setting_velocity,
        mode="interval",
        interval_range_s=(10.0, 15.0),
        params={"velocity_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5)}},
    )


@configclass
class RewardsCfg:
    """Reward terms for the MDP."""

    # -- task
    track_lin_vel_xy_exp = RewTerm(
        func=mdp.track_lin_vel_xy_exp, weight=1.0, params={"command_name": "base_velocity", "std": math.sqrt(0.25)}
    )
    track_ang_vel_z_exp = RewTerm(
        func=mdp.track_ang_vel_z_exp, weight=0.5, params={"command_name": "base_velocity", "std": math.sqrt(0.25)}
    )
    # -- penalties
    stand_still = RewTerm(
        func=mdp.stand_still,
        weight=-0.005,  # -0.01
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=".*_wheel_joint"),
            "command_name": "base_velocity",
            "std": math.sqrt(0.25),
        },
    )
    lin_vel_z_l2 = RewTerm(func=mdp.lin_vel_z_l2, weight=-2.0)
    ang_vel_xy_l2 = RewTerm(func=mdp.ang_vel_xy_l2, weight=-0.05)
    dof_torques_l2 = RewTerm(func=mdp.joint_torques_l2, weight=-1.0e-5)
    dof_acc_l2 = RewTerm(func=mdp.joint_acc_l2, weight=-2.5e-7)  # default: -2.5e-7
    action_rate_l2 = RewTerm(func=mdp.action_rate_l2, weight=-0.01)
    # feet_air_time = RewTerm(
    #     func=mdp.feet_air_time,
    #     weight=0.125,
    #     params={
    #         "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_wheel_link"),
    #         "command_name": "base_velocity",
    #         "threshold": 0.5,
    #     },
    # )
    undesired_contacts = RewTerm(
        func=mdp.undesired_contacts,
        weight=-1.0,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[".*_shoulder_link", ".*_leg_link"]),
            "threshold": 1.0,
        },
    )
    # -- optional penalties
    flat_orientation_l2 = RewTerm(func=mdp.flat_orientation_l2, weight=-0.5)
    # dof_pos_limits = RewTerm(func=mdp.joint_pos_limits, weight=0.0)
    # dof_torques_limits = RewTerm(func=mdp.applied_torque_limits, weight=0.0)
    base_target_height = RewTerm(
        func=mdp.base_height_l2,
        weight=-100.0,
        params={"target_height": 0.35082, "asset_cfg": SceneEntityCfg("robot", body_names="base_link")},
    )


@configclass
class TerminationsCfg:
    """Termination terms for the MDP."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    base_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base"), "threshold": 1.0},
    )


@configclass
class CurriculumCfg:
    """Curriculum terms for the MDP."""

    terrain_levels = CurrTerm(func=mdp.terrain_levels_vel)


##
# Environment configuration
##


@configclass
class LocomotionVelocityRoughEnvCfg(ManagerBasedRLEnvCfg):
    """Configuration for the locomotion velocity-tracking environment."""

    # Scene settings
    scene: MySceneCfg = MySceneCfg(num_envs=4096, env_spacing=2.5)
    # Basic settings
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    # MDP settings
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()
    curriculum: CurriculumCfg = CurriculumCfg()

    def __post_init__(self):
        """Post initialization."""
        # general settings
        self.decimation = 2
        self.episode_length_s = 20.0
        # simulation settings
        self.sim.dt = 0.005
        self.sim.disable_contact_processing = True
        self.sim.physics_material = self.scene.terrain.physics_material
        # update sensor update periods
        # we tick all the sensors based on the smallest update period (physics update period)
        if self.scene.height_scanner is not None:
            self.scene.height_scanner.update_period = self.decimation * self.sim.dt
        if self.scene.contact_forces is not None:
            self.scene.contact_forces.update_period = self.sim.dt

        # check if terrain levels curriculum is enabled - if so, enable curriculum for terrain generator
        # this generates terrains with increasing difficulty and is useful for training
        if getattr(self.curriculum, "terrain_levels", None) is not None:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = True
        else:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = False


@configclass
class LocomotionVelocityFlatEnvCfg(ManagerBasedRLEnvCfg):
    """Configuration for the locomotion velocity-tracking environment."""

    # Scene settings
    scene: MySceneCfg = MySceneCfg(num_envs=4096, env_spacing=2.5)
    # Basic settings
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    # MDP settings
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()
    curriculum: CurriculumCfg = CurriculumCfg()

    def __post_init__(self):
        """Post initialization."""
        # general settings
        self.decimation = 2
        self.episode_length_s = 20.0
        # simulation settings
        self.sim.dt = 0.005
        self.sim.disable_contact_processing = True
        self.sim.physics_material = self.scene.terrain.physics_material
        # update sensor update periods
        # we tick all the sensors based on the smallest update period (physics update period)
        if self.scene.height_scanner is not None:
            self.scene.height_scanner.update_period = self.decimation * self.sim.dt
        if self.scene.contact_forces is not None:
            self.scene.contact_forces.update_period = self.sim.dt

        # check if terrain levels curriculum is enabled - if so, enable curriculum for terrain generator
        # this generates terrains with increasing difficulty and is useful for training
        if getattr(self.curriculum, "terrain_levels", None) is not None:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = True
        else:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = False
