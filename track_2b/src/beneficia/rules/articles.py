"""Legal provisions applied by the rules engine.

Sources (copies kept outside the repository, see technical report):
- TJPG: Bundesgesetz vom 26. September 2025 über die Transparenz juristischer Personen und die
  Identifikation der wirtschaftlich berechtigten Personen, SR 955.3 (BBl 2025 2900).
- TJPV: Verordnung vom 12. Juni 2026, AS 2026 364.
"""

TJPG_4_1 = "TJPG art. 4 para. 1"  # 25 % of capital or votes, directly or indirectly, or other control
TJPG_4_2 = "TJPG art. 4 para. 2"  # most senior member of the managing body when nobody qualifies
TJPV_1 = "TJPV art. 1"  # direct holding of at least 25 %
TJPV_2 = "TJPV art. 2"  # indirect: more than 50 % of intermediates that hold at least 25 %
TJPV_3 = "TJPV art. 3"  # control by other means
TJPV_3_2_A = "TJPV art. 3 para. 2 let. a"  # contracts with shareholders
TJPV_3_2_E = "TJPV art. 3 para. 2 let. e"  # fiduciary relationships
TJPV_4 = "TJPV art. 4"  # acting in concert
TJPV_5 = "TJPV art. 5"  # trusts
TJPV_7 = "TJPV art. 7"  # entity controlled by a foundation
TJPV_8 = "TJPV art. 8"  # entity controlled by an association
TJPV_10 = "TJPV art. 10"  # identification of a natural person
TJPV_11 = "TJPV art. 11"  # identification of a legal entity
TJPV_12 = "TJPV art. 12"  # type of control
TJPV_13 = "TJPV art. 13"  # extent of the holding (bands)
TJPV_13_3 = "TJPV art. 13 para. 3"  # indirect control: band of the direct holding
TJPV_15 = "TJPV art. 15"  # chain of control information
TJPV_16_18 = "TJPV art. 16 to 18"  # listed companies, pension institutions, contractual funds
TJPG_7 = "TJPG art. 7"  # duty to identify and verify, information to obtain

SPECIAL_KIND_ARTICLE = {
    "foundation": TJPV_7,
    "association": TJPV_8,
    "trust": TJPV_5,
    "listed": TJPV_16_18,
    "pension": TJPV_16_18,
    "fund": TJPV_16_18,
}
