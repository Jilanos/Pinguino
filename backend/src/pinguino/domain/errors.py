"""Stable error codes and their French explanations for the UI boundary."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INSTRUMENT_CONTRACT = "INVALID_INSTRUMENT_CONTRACT"
    INVALID_DATASET_MANIFEST = "INVALID_DATASET_MANIFEST"
    INVALID_STRATEGY_DEFINITION = "INVALID_STRATEGY_DEFINITION"
    INVALID_COST_POLICY = "INVALID_COST_POLICY"
    INVALID_SIZING_POLICY = "INVALID_SIZING_POLICY"
    INVALID_RESEARCH_WINDOW = "INVALID_RESEARCH_WINDOW"
    INVALID_CAMPAIGN_CONFIG = "INVALID_CAMPAIGN_CONFIG"
    MISSING_COST_COMPONENT = "MISSING_COST_COMPONENT"
    MT5_PACKAGE_UNAVAILABLE = "MT5_PACKAGE_UNAVAILABLE"
    MT5_TERMINAL_UNAVAILABLE = "MT5_TERMINAL_UNAVAILABLE"
    MT5_TERMINAL_DISCONNECTED = "MT5_TERMINAL_DISCONNECTED"
    MT5_SYMBOL_UNAVAILABLE = "MT5_SYMBOL_UNAVAILABLE"
    MT5_HISTORY_UNAVAILABLE = "MT5_HISTORY_UNAVAILABLE"
    DATASET_NOT_FOUND = "DATASET_NOT_FOUND"
    DATASET_REJECTED = "DATASET_REJECTED"
    DATASET_COVERAGE_INSUFFICIENT = "DATASET_COVERAGE_INSUFFICIENT"
    CAMPAIGN_NOT_FOUND = "CAMPAIGN_NOT_FOUND"
    CAMPAIGN_ALREADY_RUNNING = "CAMPAIGN_ALREADY_RUNNING"
    CANDIDATE_NOT_FOUND = "CANDIDATE_NOT_FOUND"
    PREVIEW_REQUIRED = "PREVIEW_REQUIRED"
    CAMPAIGN_IMMUTABLE = "CAMPAIGN_IMMUTABLE"
    HOLDOUT_ACCESS_DENIED = "HOLDOUT_ACCESS_DENIED"
    REQUEST_TOKEN_INVALID = "REQUEST_TOKEN_INVALID"
    FOREIGN_ORIGIN_REJECTED = "FOREIGN_ORIGIN_REJECTED"


FRENCH_EXPLANATIONS: dict[ErrorCode, str] = {
    ErrorCode.INVALID_INSTRUMENT_CONTRACT: ("Le contrat d'instrument est invalide ou incomplet."),
    ErrorCode.INVALID_DATASET_MANIFEST: "Le manifeste du jeu de données est invalide.",
    ErrorCode.INVALID_STRATEGY_DEFINITION: "La définition de stratégie est invalide.",
    ErrorCode.INVALID_COST_POLICY: "La politique de coûts est invalide.",
    ErrorCode.INVALID_SIZING_POLICY: "La politique de dimensionnement est invalide.",
    ErrorCode.INVALID_RESEARCH_WINDOW: "La fenêtre de recherche est invalide.",
    ErrorCode.INVALID_CAMPAIGN_CONFIG: "La configuration de campagne est invalide.",
    ErrorCode.MISSING_COST_COMPONENT: (
        "Un composant de coût requis est absent : renseignez un profil d'approximation versionné."
    ),
    ErrorCode.MT5_PACKAGE_UNAVAILABLE: (
        "Le paquet MetaTrader 5 n'est pas disponible : le mode synthétique reste utilisable."
    ),
    ErrorCode.MT5_TERMINAL_UNAVAILABLE: (
        "Le terminal MetaTrader 5 n'est pas accessible : le mode synthétique reste utilisable."
    ),
    ErrorCode.MT5_TERMINAL_DISCONNECTED: (
        "Le terminal MetaTrader 5 est lancé mais n'est connecté à aucun serveur :"
        " connectez manuellement votre compte de démonstration."
    ),
    ErrorCode.MT5_SYMBOL_UNAVAILABLE: (
        "Ce symbole n'est pas disponible dans le terminal : ajoutez-le manuellement à la"
        " fenêtre Market Watch."
    ),
    ErrorCode.MT5_HISTORY_UNAVAILABLE: (
        "L'historique demandé n'a pas pu être lu depuis le terminal MetaTrader 5."
    ),
    ErrorCode.DATASET_NOT_FOUND: "Jeu de données introuvable.",
    ErrorCode.DATASET_REJECTED: (
        "Ce jeu de données est rejeté par le contrôle qualité : il ne peut pas servir à une"
        " campagne."
    ),
    ErrorCode.DATASET_COVERAGE_INSUFFICIENT: (
        "La couverture du jeu de données ne couvre pas la période demandée, préchauffage"
        " compris : choisissez une période plus courte."
    ),
    ErrorCode.CAMPAIGN_NOT_FOUND: "Campagne introuvable.",
    ErrorCode.CAMPAIGN_ALREADY_RUNNING: (
        "Une campagne est déjà en cours : une seule campagne s'exécute à la fois."
    ),
    ErrorCode.CANDIDATE_NOT_FOUND: "Candidat introuvable dans cette campagne.",
    ErrorCode.PREVIEW_REQUIRED: ("Prévisualisez cette configuration avant de lancer la campagne."),
    ErrorCode.CAMPAIGN_IMMUTABLE: (
        "La configuration ne peut plus être modifiée après la création de la campagne."
    ),
    ErrorCode.HOLDOUT_ACCESS_DENIED: (
        "L'échantillon final est réservé à un seul candidat figé par campagne."
    ),
    ErrorCode.REQUEST_TOKEN_INVALID: "Jeton de requête invalide pour cette session locale.",
    ErrorCode.FOREIGN_ORIGIN_REJECTED: "Origine de requête refusée : accès local uniquement.",
}


class PinguinoError(Exception):
    """Domain error carrying a stable code and a French explanation."""

    def __init__(self, code: ErrorCode, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else str(code))

    @property
    def french(self) -> str:
        return FRENCH_EXPLANATIONS[self.code]
