"""Shared regex and vocabulary definitions for FSR v2 preprocessing."""

import re

NOT_APPLICABLE = [
    r'(?i)this equipment is not applicable',
    r'(?i)not applicable for this outage',
    r'(?i)no work performed on this (?:unit|equipment)',
    r'(?i)not included in (?:this )?scope',
]

HEADER = r'(GAS TURBINE|GENERATOR|STEAM TURBINE|EXCITER)\s*\(\s*(\d{3}[A-Z]?\d{3}|GG\d{4,6})\s*\|\s*(SY\d{7})\)'

GT_LABELS = [
    r'Gas\s*Turbine\s*(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
    r'Assoc(?:iated)?\.?\s*Turbine\s*[:#]?\s*(\d{6})',
]
GEN_LABELS = [
    r'Gen(?:erator)?\s*(?:Field\s*)?(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]\d{3})',
    r'Generator\s*#\s*(\d{3}[A-Z]\d{3})',
    r'(?:Equipment\s+)?Generator\s+(?:No|Number)\.?\s*[:#]?\s*(\d{3}[A-Z]\d{3})',
    r'(GG\d{4,6})\s*\|\s*SY\d{7}',
]
GEN_EQUIPMENT_ID_SN_PAIR = (
    r'(?is)\bEquipment\s+ID\s*[:#]?\s*SY\d{7}\s*'
    r'Equipment\s+(?:SN|Serial(?:\s*(?:No|#|Number))?)\s*[:#]?\s*'
    r'(GG\d{4,6})\b'
)
ST_LABELS = [
    r'Steam\s*Turbine\s*(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
]
GENERIC_LABELS = [
    r'Equipment\s*Serial\s*#?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
    r'\bESN\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
]

GEN_FORMS = ['D3162041', 'D3162043', 'D3162044', 'D316218', 'D316303', 'D316402',
             'D316403', 'D316501', 'D316512', 'D300001', 'D306301', 'D306302',
             'D309102', 'D309301', 'D309302', 'D315102']
GT_FORMS = ['GT3225', 'GT9245', 'GT9386', 'GT9390', 'GT4050', 'GT1040', 'GT71F040', 'GT71F045']

GEN_SIGNATURES = [
    'armature winding resistance', 'armature insulation', 'hipotential testing',
    'stator voltage', 'polarization index', 'power mva', 'max h2 pressure',
    'collector end', 'dc leakage', 'stator insulation resistance',
    'endwinding', 'end winding', 'retaining ring', 'field winding',
    'el-cid', 'el cid', 'wedge tightness', 'stator core',
    'hydrogen seal', 'diode wheel', 'partial discharge', 'stator rewind',
    'core lamination', 'generator specialist',
]

GT_SIGNATURES = [
    'combustion liner', 'combustion can', 'transition piece', 'fuel nozzle',
    'crossfire tube', 'cross fire tube', 'flow sleeve',
    'inlet guide vane', 'compressor discharge', 'hot gas path',
    'stage 1 nozzle', 'stage 1 bucket', 'stage 1 shroud',
    'stage 2 nozzle', 'stage 2 bucket', 'stage 2 shroud',
    'stage 3 nozzle', 'stage 3 bucket', 'stage 3 shroud',
    'wheelspace', 'load coupling', 'load gear',
    'igv calibration', 'bleed valve', 'spark plug', 'flame detector',
    'wheel space', 'dln tuning', 'fsnl', 'water wash',
    'exhaust thermocouple', 'gas turbine executive', 'fired hours',
    'compressor blade', 'compressor vane', 'turbine wheel',
]

START_LABELS = [r'(?:Job|Outage)\s*Start\s*Date\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']
END_LABELS = [r'(?:Job|Outage)\s*(?:End|Completion)\s*Date\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']
ISSUED_LABELS = [r'(?:Approved|Report\s*Issued|Date\s*Issued)\s*(?:Date)?\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']

DATE_STOP = r'\s{2,}|Oracle|Prepared|Approved|Equipment|Report|Contents|Generator|Gas\s*Turbine|Job\b'

UNNUMBERED_EQUIP_HDR = r'(?im)^(GAS\s+TURBINE|GENERATOR|STEAM\s+TURBINE|EXCITER)\s*$'
UNNUMBERED_TITLED_HDR = (
    r'(?im)^(Generator|Gas\s+Turbine|Steam\s+Turbine)\s+'
    r'(?:Section|Report|Inspection)\b.*$'
)
SECTION_HDR = r'(?im)^\s*#{0,3}\s*(\d+)[ \t]+(GAS\s+TURBINE|TURBINE|GENERATOR|STEAM\s+TURBINE|EXCITER)\s*$'
SECTION_HDR_GENERAL_ROOT = r'(?im)^\s*#{0,3}\s*(\d+)[ \t]+(Summary|Technical)[ \t]*$'
UNNUMBERED_GENERAL_ROOT = r'(?im)^\s*#{0,3}\s*OUTAGE[ \t]+DETAILS[ \t]*$'
SECTION_HDR_GEN_KEYWORD = (
    r'(?im)^\s*#{0,3}[ \t]*(\d+)[ \t]+(Electrical[ \t]+System|Electrical|Electrification)[ \t]*$'
)
SECTION_HDR_SUB_REPORTS = r'(?im)^\s*#{0,3}\s*(\d+)[ \t]+Sub\s+Reports\s*$'
SECTION_HDR_TURBINE_KEYWORD = (
    r'(?im)^\s*#{0,3}\s*(\d+)[ \t]+'
    r'(PIPO|Control[ \t]+System|QCP|Quality[ \t]+Checkpoint)'
    r'(?:[ \t]*\([^\n)]*\))?[ \t]*$'
)
SECTION_HDR_ATTACHMENT = (
    r'(?im)^\s*#{0,3}\s*(\d+)[ \t]+'
    r'(Attachments?|Appendix|Sub[ \t]+Reports?)[ \t]*$'
)
SUBSEC_GEN = (
    r'(?m)^(?:#{1,3}[ \t]+)?(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)[ \t]+Generator(?:[ \t]+([^\n]+))?$'
)
SUBSEC_GEN_KEYWORD = (
    r'(?m)^(?:#{1,3}[ \t]+)?(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)[ \t]+'
    r'(?:Electrical|Electrification|DC[ \t]+Leakage|Field|EL[ \t]+CID|LCI)(?:[ \t]+([^\n]+))?$'
)
SUBSEC_TURBINE = (
    r'(?m)^(?:#{1,3}[ \t]+)?(\d{1,2}(?:\.\d{1,2})+)[ \t]+Turbine(?:[ \t]+([^\n]+))?$'
)
SUBSEC_TURBINE_KEYWORD = (
    r'(?m)^(?:#{1,3}[ \t]+)?(\d{1,2}(?:\.\d{1,2})+)[ \t]+'
    r'(?:PIPO|Control[ \t]+System|QCP)$'
)
SUBSEC_GT = (
    r'(?m)^(?:#{1,3}[ \t]+)?(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)[ \t]+'
    r'(?:Gas[ \t]+Turbine|Compressor|Combustion|Inlet)(?:[ \t]+([^\n]+))?$'
)
SUBSEC_ATTACHMENT = (
    r'(?m)^(?:#{1,3}[ \t]+)?(\d{1,2}(?:\.\d{1,2})*)[ \t]*'
    r'(?:Attachments?|Appendix)\b(?:[ \t]+([^\n]+))?$'
)
SUBSEC_GENERIC = r'(?m)^(?:#{1,3}[ \t]+)?(\d{1,2}(?:\.\d{1,2})+)[ \t]+([^\n]+)$'

DOC_SUMMARY_PATTERN = re.compile(
    r"\bexecutive\s+summary\b|\binspection\s+summary\b|\bsummary\b",
    re.IGNORECASE,
)
DOC_SUMMARY_NOISE_PATTERN = re.compile(
    r"^[\s_\-\.\|]*$|^table\s+of\s+contents?$|^contents?$",
    re.IGNORECASE,
)