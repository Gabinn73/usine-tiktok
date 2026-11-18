# Sources musicales

Toutes les musiques sont des **œuvres du domaine public**, transcrites en MIDI par le
[Mutopia Project](https://www.mutopiaproject.org/). La licence de chaque fichier a été vérifiée
sur sa fiche Mutopia le 18/11/2026 : **Public Domain** pour les quatre.

| Clé (`--music`)        | Œuvre                                                        | Compositeur   | Fichier                                    | Fiche Mutopia | Licence |
|------------------------|--------------------------------------------------------------|---------------|--------------------------------------------|---------------|---------|
| `grieg_roi_montagne`   | Dans l'antre du roi de la montagne (Peer Gynt, op. 46 n° 4)  | Edvard Grieg  | `Dans_l_antre_du_roi_de_la_montagne.mid`   | [id=1888](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=1888) | Public Domain |
| `mozart_alla_turca`    | Rondo alla turca (Sonate KV 331, 3e mouvement)               | W. A. Mozart  | `KV331_3_RondoAllaTurca.mid`               | [id=108](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=108)   | Public Domain |
| `joplin_entertainer`   | The Entertainer                                              | Scott Joplin  | `entertainer.mid`                          | [id=263](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=263)   | Public Domain |
| `joplin_maple_leaf`    | Maple Leaf Rag                                               | Scott Joplin  | `maple.mid`                                | [id=23](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=23)     | Public Domain |

## Rendu audio
Les MIDI sont rendus en WAV par **FluidSynth** avec la soundfont **FluidR3_GM**
(Frank Wen, licence **MIT** — paquet Debian/Ubuntu `fluid-soundfont-gm`,
`/usr/share/sounds/sf2/FluidR3_GM.sf2`). Le rendu est mis en cache dans `output/.cache/musique/`.

Les bruitages (chocs, battements, montée, fanfare, carillon) sont entièrement synthétisés en code
(`usine/audio.py`, numpy) : aucun enregistrement externe.

## Ajouter un morceau
1. Trouver l'œuvre sur Mutopia et vérifier la licence sur sa fiche (`Public Domain` de préférence ;
   `CC BY` / `CC BY-SA` imposent une attribution dans la description de la vidéo).
2. Télécharger le `.mid` dans ce dossier, ajouter une entrée dans `MUSIC` (`usine/audio.py`)
   et une ligne dans ce tableau.
