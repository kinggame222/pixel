# Guide d'Automatisation de Minage

Ce guide vous explique comment utiliser le système d'automatisation pour créer des chaînes de production efficaces dans votre monde minier.

## Table des Matières
1. [Concepts de Base](#concepts-de-base)
2. [Coffres de Stockage](#coffres-de-stockage)
3. [Convoyeurs](#convoyeurs)
4. [Extracteurs d'Items](#extracteurs-ditems)
5. [Processeurs de Minerai](#processeurs-de-minerai)
6. [Création d'une Chaîne de Production](#création-dune-chaîne-de-production)
7. [Placement Rapide de Convoyeurs](#placement-rapide-de-convoyeurs)
8. [Conseils et Astuces](#conseils-et-astuces)

## Concepts de Base

Le système d'automatisation se compose de quatre éléments principaux :
- **Coffres de stockage** : Pour stocker vos ressources
- **Convoyeurs** : Pour transporter les ressources
- **Extracteurs** : Pour extraire les ressources des coffres et les placer sur les convoyeurs
- **Processeurs** : Pour transformer les ressources brutes en matériaux de valeur

## Coffres de Stockage

### Caractéristiques
- Taille : 3x3 blocs
- Capacité : 200 objets

### Comment les Utiliser
1. **Placement** : Appuyez sur "N" pour ajouter un coffre à votre inventaire, puis cliquez-droit sur un emplacement vide pour le placer.
2. **Interaction** : Cliquez-gauche sur un coffre pour ouvrir son interface.
3. **Ajouter des objets** : Faites glisser des objets de votre inventaire vers le coffre, ou cliquez-droit avec un objet sélectionné.
4. **Retirer des objets** : Cliquez-gauche sur un objet dans le coffre pour le prendre, puis faites-le glisser vers votre inventaire.

### Astuces
- Les coffres sont idéaux pour servir de tampons dans vos systèmes d'automatisation.
- Placez des coffres à des points stratégiques de votre chaîne de production.

## Convoyeurs

### Types de Convoyeurs
1. **Convoyeur Standard** : Taille 2x2, déplace les objets horizontalement.
2. **Convoyeur Vertical** : Taille 2x2, déplace les objets verticalement.

### Comment les Utiliser
1. **Placement** :
   - Appuyez sur "V" pour ajouter un convoyeur standard à votre inventaire.
   - Appuyez sur "B" pour ajouter un convoyeur vertical à votre inventaire.
   - Cliquez-droit sur un emplacement vide pour placer le convoyeur.

2. **Changer la Direction** :
   - Cliquez-droit sur un convoyeur placé pour changer sa direction.
   - La direction du convoyeur est indiquée par une flèche.
   - Séquence de rotation : Droite → Bas → Gauche → Haut → Droite...

3. **Placer des Objets** :
   - Les objets peuvent être placés directement sur un convoyeur en cliquant-droit avec un objet.
   - Les extracteurs et processeurs peuvent placer automatiquement des objets sur les convoyeurs.

### Directions des Convoyeurs
- **0 (Droite)** : Les objets se déplacent vers la droite
- **1 (Bas)** : Les objets se déplacent vers le bas
- **2 (Gauche)** : Les objets se déplacent vers la gauche
- **3 (Haut)** : Les objets se déplacent vers le haut

### Règles de Mouvement
1. Les objets se déplacent dans la direction du convoyeur.
2. Les objets peuvent passer d'un convoyeur à un autre si la position suivante est un convoyeur.
3. Les objets peuvent passer d'un convoyeur à un coffre ou à un processeur.
4. Si un objet atteint la fin d'un convoyeur sans destination valide, il reste bloqué jusqu'à ce qu'une destination soit disponible.

## Extracteurs d'Items

### Caractéristiques
- Taille : 2x2 blocs
- Fonction : Extraire des objets d'un coffre et les placer sur un convoyeur.

### Comment les Utiliser
1. **Placement** : Appuyez sur "X" pour ajouter un extracteur à votre inventaire, puis cliquez-droit sur un emplacement vide pour le placer.
2. **Configuration** : Placez l'extracteur à côté d'un coffre et d'un convoyeur :
   - L'extracteur doit toucher le coffre d'un côté.
   - L'extracteur doit toucher le convoyeur du côté opposé.

### Comportement
1. L'extracteur vérifie périodiquement le coffre connecté.
2. S'il trouve des objets, il les extrait un par un.
3. L'extracteur place les objets extraits sur le convoyeur connecté.

## Processeurs de Minerai

### Caractéristiques
- Taille : Variable (le processeur de minerai fait 4x6 blocs)
- Fonction : Transformer les ressources brutes en matériaux raffinés

### Comment les Utiliser
1. **Placement** : Appuyez sur "P" pour ajouter un processeur de minerai à votre inventaire, puis cliquez-droit sur un emplacement vide pour le placer.
2. **Interaction** : Cliquez-gauche sur un processeur pour ouvrir son interface.
3. **Ajouter des Ressources** : Déposez des minerais bruts dans l'emplacement d'entrée.
4. **Récupérer les Produits** : Prenez les produits transformés dans l'emplacement de sortie.

### Recettes de Traitement
- Minerai de fer → Lingot de fer
- Minerai de diamant → Cristal de diamant
- Pierre → Gravier (x2)
- Gravier → Sable

## Création d'une Chaîne de Production

Voici comment créer une chaîne de production de base :

### Exemple : Usine de Traitement Automatique du Fer

1. **Mise en place du stockage d'entrée** :
   - Placez un coffre de stockage (3x3) pour y déposer vos minerais bruts.

2. **Configuration de l'extraction** :
   - Placez un extracteur (2x2) adjacent au coffre d'entrée.
   - Assurez-vous qu'un des côtés de l'extracteur touche le coffre.

3. **Création du réseau de convoyeurs** :
   - Placez un convoyeur (2x2) adjacent à l'extracteur, du côté opposé au coffre.
   - Étendez le réseau de convoyeurs vers votre processeur de minerai.
   - Utilisez des convoyeurs verticaux si nécessaire pour les changements de hauteur.

4. **Installation du processeur** :
   - Placez un processeur de minerai (4x6) à la fin de votre ligne de convoyeurs.
   - Assurez-vous que la partie d'entrée du processeur touche le dernier convoyeur.

5. **Mise en place du système de sortie** :
   - Placez un convoyeur adjacent à la sortie du processeur.
   - Étendez ce convoyeur vers un coffre de stockage pour les produits finis.
   - Placez un coffre de stockage à la fin du convoyeur de sortie.

### Fonctionnement :

1. Les minerais bruts sont stockés dans le coffre d'entrée.
2. L'extracteur prélève les minerais et les place sur le convoyeur.
3. Les convoyeurs transportent les minerais jusqu'au processeur.
4. Le processeur transforme les minerais en lingots.
5. Les lingots sont transportés par convoyeur vers le coffre de sortie.
6. Les produits finis s'accumulent dans le coffre de sortie.

## Placement Rapide de Convoyeurs

Pour faciliter la construction de longues chaînes de convoyeurs, un système de placement rapide a été implémenté.

### Comment l'Utiliser
1. **Activer/Désactiver** : Appuyez sur `Z` pour activer ou désactiver le mode de placement rapide.
   - Un message de confirmation apparaîtra dans la console.
   - Une prévisualisation des convoyeurs apparaîtra lorsque vous déplacerez votre souris.

2. **Changer de Mode** : Appuyez sur `R` pour alterner entre les différents modes de placement :
   - **Ligne Droite** : Place les convoyeurs en ligne droite (mode par défaut).
   - **Diagonale** : Place les convoyeurs en diagonale (pratique pour contourner des obstacles).
   - **Zig-Zag** : Alterne les directions pour créer un chemin en zig-zag (utile pour les niveaux différents).
   - Un message dans la console indique le mode actif.

3. **Changer la Direction** : Appuyez sur `TAB` pour changer la direction de placement :
   - **Droite** → **Bas** → **Gauche** → **Haut**
   - La direction est indiquée par des flèches dans la prévisualisation.
   - Un message dans la console indique la direction actuelle.

4. **Placement** : 
   - Sélectionnez un convoyeur dans votre inventaire.
   - Activez le mode de placement rapide avec `Z`.
   - Pointez vers l'emplacement où vous souhaitez commencer votre chaîne.
   - Cliquez-droit pour placer automatiquement la série de convoyeurs.
   - Les convoyeurs seront placés jusqu'à rencontrer un obstacle ou épuiser votre inventaire.

### Dépannage du Système de Placement Rapide

Si le système de placement rapide ne fonctionne pas :

1. **Vérifiez que vous avez activé le mode** :
   - Appuyez sur `Z` et confirmez que le message "Mode de placement rapide de convoyeurs activé" apparaît.
   
2. **Vérifiez que vous avez des convoyeurs sélectionnés** :
   - Le système ne fonctionne qu'avec des convoyeurs standards ou verticaux.
   - Vous devez avoir l'un de ces types sélectionné dans votre barre d'inventaire.

3. **Vérifiez l'espace disponible** :
   - Un aperçu transparent devrait montrer où les convoyeurs seront placés.
   - Si aucun aperçu n'apparaît, il n'y a pas assez d'espace pour placer des convoyeurs.

4. **Redémarrez le jeu** :
   - Si les problèmes persistent, essayez de sauvegarder et redémarrer le jeu.

### Prévisualisation
Lorsque le mode est actif, vous verrez une prévisualisation semi-transparente des convoyeurs qui seront placés. Cela vous permet de vérifier le chemin avant de confirmer le placement.

### Avantages
- Construction rapide de systèmes complexes
- Économie de temps et d'efforts
- Placement précis grâce à la prévisualisation
- Possibilité de créer des chemins variés avec les différents modes

Cette fonctionnalité est particulièrement utile pour construire de grands systèmes d'automatisation où de nombreux convoyeurs doivent être placés à la suite.

## Conseils et Astuces

1. **Planifiez votre espace** - Les structures d'automatisation prennent plus de place que prévu. Réservez suffisamment d'espace pour vos chaînes de production.

2. **Utilisez la rotation des convoyeurs** - Cliquez-droit sur un convoyeur pour modifier sa direction jusqu'à obtenir l'orientation désirée.

3. **Créez des tampons** - Placez des coffres intermédiaires dans votre chaîne pour éviter les blocages en cas de production excessive.

4. **Organisez par étages** - Utilisez les convoyeurs verticaux pour créer des systèmes multi-niveaux et économiser de l'espace horizontal.

5. **Séparez vos chaînes** - Créez des chaînes de production distinctes pour chaque type de ressource afin d'éviter les mélanges.

6. **Testez progressivement** - Construisez et testez votre système par sections plutôt que d'essayer de tout construire en une fois.

7. **Équilibrez l'approvisionnement** - Assurez-vous que vos convoyeurs ne sont pas surchargés d'un côté et vides de l'autre.

## Raccourcis Clavier

- **N** : Ajouter un coffre de stockage à l'inventaire
- **V** : Ajouter un convoyeur standard à l'inventaire
- **B** : Ajouter un convoyeur vertical à l'inventaire
- **X** : Ajouter un extracteur à l'inventaire
- **P** : Ajouter un processeur de minerai à l'inventaire
- **Z** : Activer/Désactiver le mode de placement rapide
- **R** : Alterner entre les modes de placement rapide
- **TAB** : Changer la direction de placement rapide

## Solutions aux Problèmes Courants

1. **Les objets ne se déplacent pas sur le convoyeur**
   - Vérifiez que le convoyeur est orienté dans la bonne direction
   - Assurez-vous que le chemin n'est pas bloqué

2. **L'extracteur ne prend pas d'objets**
   - Vérifiez qu'il est correctement positionné à côté du coffre
   - Assurez-vous que le coffre contient des objets

3. **Le processeur ne traite pas les minerais**
   - Vérifiez que vous utilisez le bon type de minerai
   - Assurez-vous que l'emplacement de sortie n'est pas bloqué
