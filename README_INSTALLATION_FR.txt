EXPORT DU CALQUE « MUD ROADS » FOXHOLE
=======================================

Cette modification intègre directement l’export d’un PNG mondial transparent
contenant les chemins piétons, les places et les surfaces de terre tassée.

INSTALLATION
------------

1. Copiez 5_finalize_exports.py à la racine de fh_map_exporter.

2. Copiez utils/config.py dans le sous-dossier utils.

3. Vérifiez que les couches du terrain ont déjà été extraites :

       export/_layers/

   Si ce dossier est absent, exécutez d’abord :

       python 1_export.py

4. Lancez ensuite la finalisation habituelle :

       python 5_finalize_exports.py

SORTIE
------

Le fichier est créé ici :

    export/_final/assembly/mud_roads.png

Il mesure 20528 x 12704 px lorsque les 55 régions sont présentes. Son fond est
transparent et son placement correspond directement à la grande carte.

La couleur par défaut est #B7A491 et peut être modifiée dans
utils/config.py via MUD_ROAD_COLOR.


EXPORT DE TOUTES LES COUCHES
-----------------------------

Toutes les couches Landscape sont également créées séparément ici :

    export/_final/landscape_layers/<nom_de_couche>.png

Chaque fichier est en pleine résolution mondiale, coloré selon LAYER_COLORS et
transparent selon le poids original de la couche. Cela inclut notamment Grass,
Snow, Sand, Dirt, Road, TownStone, MuddyGround, Rock, Stone et Ice.
