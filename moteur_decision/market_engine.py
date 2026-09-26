# -*- coding: utf-8 -*-
"""Marchés dérivables du modèle de buts. Aucun prix ni choix de pari ici."""
from __future__ import annotations
from .statistical_model import ModelOutput

def _event(m, predicate):
    return sum(p for h,row in enumerate(m) for a,p in enumerate(row) if predicate(h,a))

def _ou(m, line):
    over = _event(m, lambda h,a: h+a > line)
    return over, 1.0-over

def _team_ou(m, line, home=True):
    over = _event(m, (lambda h,a: h > line) if home else (lambda h,a: a > line))
    return over, 1.0-over

def _half_result(m):
    return (_event(m, lambda h,a: h>a), _event(m, lambda h,a: h==a), _event(m, lambda h,a: h<a))

def _btts(m):
    yes = _event(m, lambda h,a: h>=1 and a>=1)
    return yes, 1.0-yes

def _clean(m, home=True):
    return _event(m, (lambda h,a: a==0) if home else (lambda h,a: h==0))

def _exact_goals(m):
    out={f"exact_goals_{n}":_event(m,lambda h,a,n=n:h+a==n) for n in range(6)}
    out["exact_goals_6_plus"]=_event(m,lambda h,a:h+a>=6)
    return out

def derive_goal_markets(model: ModelOutput, handicap_lines=()):
    m=model.score_matrix
    w,d,l=_half_result(m)
    out={"victoire":w,"nul":d,"defaite":l,"dc_1X":w+d,"dc_X2":d+l,"dc_12":w+l}
    by,bn=_btts(m); out.update({"btts_oui":by,"btts_non":bn})
    for x in range(6):
        o,u=_ou(m,x+0.5); out[f"over_{x}_5"],out[f"under_{x}_5"]=o,u
    for x in (0,1):
        o,u=_team_ou(m,x,True); out[f"buts_dom_over_{x}_5"],out[f"buts_dom_under_{x}_5"]=o,u
        o,u=_team_ou(m,x,False); out[f"buts_ext_over_{x}_5"],out[f"buts_ext_under_{x}_5"]=o,u
    out["clean_sheet_dom"],out["clean_sheet_ext"]=_clean(m,True),_clean(m,False)
    out.update(_exact_goals(m))
    for line in handicap_lines:
        h=_event(m,lambda a,b,line=line:a+line>b)
        dr=_event(m,lambda a,b,line=line:a+line==b)
        ex=_event(m,lambda a,b,line=line:a+line<b)
        out[f"handicap_3way_{line:g}_dom"],out[f"handicap_3way_{line:g}_nul"],out[f"handicap_3way_{line:g}_ext"]=h,dr,ex

    if model.score_matrix_first_half is not None:
        fh,fd,fa=_half_result(model.score_matrix_first_half)
        out.update({"mi_temps_victoire":fh,"mi_temps_nul":fd,"mi_temps_defaite":fa,
                    "mi_temps_dc_1X":fh+fd,"mi_temps_dc_X2":fd+fa,"mi_temps_dc_12":fh+fa})
        bt,bn=_btts(model.score_matrix_first_half)
        out.update({"mi_temps_btts_oui":bt,"mi_temps_btts_non":bn,
                    "mi_temps_clean_sheet_dom":_clean(model.score_matrix_first_half,True),
                    "mi_temps_clean_sheet_ext":_clean(model.score_matrix_first_half,False)})
        for x in range(6):
            o,u=_ou(model.score_matrix_first_half,x+0.5); out[f"mi_temps_over_{x}_5"],out[f"mi_temps_under_{x}_5"]=o,u
    if model.score_matrix_second_half is not None:
        sh,sd,sa=_half_result(model.score_matrix_second_half)
        out.update({"2e_mi_temps_victoire":sh,"2e_mi_temps_nul":sd,"2e_mi_temps_defaite":sa,
                    "2e_mi_temps_dc_1X":sh+sd,"2e_mi_temps_dc_X2":sd+sa,"2e_mi_temps_dc_12":sh+sa})
        bt,bn=_btts(model.score_matrix_second_half)
        out.update({"2e_mi_temps_btts_oui":bt,"2e_mi_temps_btts_non":bn,
                    "2e_mi_temps_clean_sheet_dom":_clean(model.score_matrix_second_half,True),
                    "2e_mi_temps_clean_sheet_ext":_clean(model.score_matrix_second_half,False)})
        for x in range(6):
            o,u=_ou(model.score_matrix_second_half,x+0.5); out[f"2e_mi_temps_over_{x}_5"],out[f"2e_mi_temps_under_{x}_5"]=o,u
    return out
