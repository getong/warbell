//! Footstep SOUNDS — turns each [`Footfall`](crate::footing::Footfall) into an [`AudioCue`]. The
//! footfall itself (gait-phase-locked hero steps, the landing touchdown, distance-paced NPC steps)
//! and the surface under the boot come from [`crate::footing`], so the step you hear is the step
//! the dust and the print show. The [`super::sfx`] consumer picks the surface's clip set.

use bevy::prelude::*;

use crate::footing::{Footfall, Stepper};

use super::AudioCue;

pub(crate) fn hero_footsteps(mut steps: MessageReader<Footfall>, mut cues: MessageWriter<AudioCue>) {
    for f in steps.read() {
        match f.who {
            Stepper::Hero => cues.write(AudioCue::Footstep { surface: f.surface, gait: f.gait, landing: false }),
            Stepper::HeroLanding { .. } => cues.write(AudioCue::Footstep { surface: f.surface, gait: 1.0, landing: true }),
            Stepper::Npc { audible: true } => cues.write(AudioCue::NpcStep { surface: f.surface, at: f.at }),
            Stepper::Npc { audible: false } => continue,
        };
    }
}
