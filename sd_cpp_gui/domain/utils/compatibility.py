"""
Service to handle Base Model compatibility logic.
"""

from typing import Literal, Optional

CompatibilityStatus = Literal[
    "compatible", "possible", "incompatible", "unknown"
]


class CompatibilityService:
    """Group definitions to map specific versions to families"""

    FAMILIES = {
        "SD1": ["SD 1.4", "SD 1.5", "SD 1.5 LCM", "SD 1.5 Hyper"],
        "SD2": [
            "SD 2.0",
            "SD 2.0 768",
            "SD 2.1",
            "SD 2.1 768",
            "SD 2.1 Unclip",
        ],
        "SDXL": [
            "SDXL 0.9",
            "SDXL 1.0",
            "SDXL 1.0 LCM",
            "SDXL Distilled",
            "SDXL Hyper",
            "SDXL Lightning",
            "SDXL Turbo",
        ],
        "Pony": ["Pony", "Pony V6", "Pony V7"],
        "Illustrious": ["Illustrious"],
        "Flux": ["Flux.1 D", "Flux.1 S", "Flux.1 Krea"],
        "SVD": ["SVD", "SVD XT"],
    }
    CROSS_COMPATIBILITY = {
        "SDXL": ["Pony", "Illustrious", "Anime"],
        "Pony": ["SDXL"],
        "Illustrious": ["SDXL"],
    }

    @classmethod
    def get_family(cls, base_model_name: Optional[str]) -> str:
        """Determines the broad family of a specific base model string.

        Logic: Matches model name against known families."""
        if not base_model_name:
            return "Unknown"
        name = base_model_name.strip()
        for family, members in cls.FAMILIES.items():
            if name in members or any((m in name for m in members)):
                return family
        if "SDXL" in name:
            return "SDXL"
        if "1.5" in name:
            return "SD1"
        if "Pony" in name:
            return "Pony"
        return "Unknown"

    @classmethod
    def check(
        cls, model_base: Optional[str], resource_base: Optional[str]
    ) -> CompatibilityStatus:
        """
        Checks compatibility between a Checkpoint Base
        and a Resource (LoRA) Base.

        Logic: Compares model families to determine compatibility status.
        """
        if not model_base or not resource_base:
            return "unknown"
        if model_base == resource_base:
            return "compatible"
        model_fam = cls.get_family(model_base)
        res_fam = cls.get_family(resource_base)
        if model_fam == "Unknown" or res_fam == "Unknown":
            return "unknown"
        if model_fam == res_fam:
            return "compatible"
        if res_fam in cls.CROSS_COMPATIBILITY.get(model_fam, []):
            return "possible"
        return "incompatible"

    @staticmethod
    def get_status_icon(status: CompatibilityStatus) -> str:
        """Logic: Returns icon corresponding to compatibility status."""
        if status == "compatible":
            return "✅"
        if status == "possible":
            return "⚠️"
        if status == "unknown":
            return "❓"
        return "⛔"
