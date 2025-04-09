# Guide d'Utilisation: Automatisation et Transport d'Items

Ce guide vous explique comment faire circuler des objets automatiquement dans votre système d'automatisation.

## 1. Mise en Place d'un Système Basique

Pour faire fonctionner votre système d'automatisation, vous avez besoin de plusieurs éléments :

- **Coffres de stockage** (3x3)
- **Convoyeurs** (2x2)
- **Extracteurs** (2x2)
- **Processeurs** pour transformer les ressources

### Étape 1: Construire un Coffre de Stockage Source

1. Appuyez sur `N` pour ajouter un coffre à votre inventaire
2. Placez le coffre en cliquant-droit sur un emplacement vide
3. Cliquez-gauche sur le coffre pour l'ouvrir
4. Déposez quelques items dans le coffre (par exemple, du minerai de fer)

### Étape 2: Placer un Extracteur

1. Appuyez sur `X` pour ajouter un extracteur à votre inventaire
2. Placez l'extracteur ADJACENT au coffre source (il doit toucher un côté du coffre)
3. L'orientation est importante : l'extracteur doit faire face à la direction où vous voulez que les items sortent

### Étape 3: Construire un Réseau de Convoyeurs

1. Appuyez sur `Z` pour activer le mode de placement rapide des convoyeurs
2. Appuyez sur `R` pour sélectionner le mode de placement (ligne droite, diagonale, etc.)
3. Appuyez sur `TAB` pour définir la direction des convoyeurs
4. Placez le premier convoyeur ADJACENT à la sortie de l'extracteur
5. Continuez à étendre le réseau jusqu'à votre destination

### Étape 4: Placer un Coffre de Destination ou une Machine

1. À la fin de votre ligne de convoyeurs, placez un autre coffre ou une machine (comme un processeur de minerai)

## 2. Comment les Items se Déplacent

Les items se déplacent automatiquement dans votre système selon ces règles:

1. **Extraction**: L'extracteur vérifie périodiquement le coffre source et prélève automatiquement des items
2. **Transport**: Les items prélevés sont placés sur le convoyeur adjacent et se déplacent dans la direction définie
3. **Destination**: Lorsqu'un item atteint la fin d'un convoyeur, il vérifie la destination:
   - Si c'est un autre convoyeur, l'item continue son chemin
   - Si c'est un coffre, l'item est automatiquement stocké
   - Si c'est une machine, l'item est placé dans l'emplacement d'entrée si possible

## 3. Visualisation des Items

Les items sur les convoyeurs sont représentés visuellement par:

- De petits carrés colorés qui se déplacent sur le convoyeur dans la direction définie
- La couleur correspond au type d'item
- La vitesse de déplacement est fixe (définie par le système)

Pour voir des items se déplacer sur vos convoyeurs:

1. Assurez-vous d'avoir des items dans votre coffre source
2. Vérifiez que l'extracteur est correctement placé (adjacent au coffre)
3. Vérifiez que les convoyeurs sont tous connectés et orientés dans la bonne direction
4. Attendez quelques secondes - les extracteurs fonctionnent périodiquement

## 4. Dépannage des Problèmes Courants

### Les items n'apparaissent pas sur les convoyeurs:

1. **Vérifiez le coffre source**: Assurez-vous qu'il contient des items.
2. **Vérifiez l'extracteur**: 
   - Est-il correctement placé à côté du coffre?
   - Est-il orienté vers le premier convoyeur?
3. **Vérifiez les convoyeurs**:
   - Sont-ils tous orientés dans la bonne direction?
   - Y a-t-il des espaces ou des interruptions dans la ligne?

### Les items s'arrêtent au milieu du parcours:

1. **Vérifiez l'orientation des convoyeurs**: Un convoyeur mal orienté peut bloquer le flux.
2. **Vérifiez les connexions**: Les convoyeurs doivent être adjacents les uns aux autres.
3. **Vérifiez les destinations**: La machine ou le coffre de destination est-il plein?

### Les items disparaissent:

1. **Vérifiez les blocs finaux**: Les items peuvent tomber si le convoyeur mène au vide.
2. **Vérifiez la capacité**: Les machines et coffres de destination ont une capacité limitée.

## 5. Conseils Avancés

### Création de Filtres et Tris

Pour trier différents types d'items, vous pouvez créer des bifurcations dans votre système de convoyeurs:

1. Placez des extracteurs sur différents côtés d'un même coffre
2. Connectez chaque extracteur à un réseau de convoyeurs différent
3. Chaque réseau peut mener à une machine ou un stockage spécifique

### Optimisation de la Vitesse

Pour optimiser la vitesse de traitement:

1. Utilisez plusieurs extracteurs pour les coffres contenant beaucoup d'items
2. Maintenez des lignes de convoyeurs courtes quand c'est possible
3. Utilisez des coffres intermédiaires comme tampons pour équilibrer le flux

## 6. Exemple Illustré

Voici un exemple de configuration efficace:

