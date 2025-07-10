# 📘 Documentation des Modèles de Données de PayDay

Cette documentation décrit les modèles de données de l'application Django **PayDay**, conçue pour gérer la paie, les congés, les avances sur salaire et d'autres aspects liés aux ressources humaines. Chaque modèle est accompagné d'une explication de son rôle, de son importance, d'une structure hiérarchique claire et d'une description des champs associés. Les explications sont en français, tandis que les noms des modèles et des champs restent inchangés. Un glossaire des types de données est fourni à la fin.

---

## Table des matières

- [Introduction](#introduction)
- [Modèles de Données](#modèles-de-données)
  - [User](#user)
  - [Group](#group)
  - [Permission](#permission)
  - [ContentType](#contenttype)
  - [Employee](#employee)
  - [TypeOfLeave](#typeofleave)
  - [EarlyLeave](#earlyleave)
  - [Leave](#leave)
  - [LegalItem](#legalitem)
  - [Item](#item)
  - [SpecialEmployeeItem](#specialemployeeitem)
  - [Payroll](#payroll)
  - [ItemPaid](#itempaid)
  - [AdvanceSalary](#advancesalary)
  - [AdvanceSalaryPayment](#advancesalarypayment)
  - [PaidEmployee](#paidemployee)
  - [Grade](#grade)
  - [Status](#status)
  - [Branch](#branch)
  - [Agreement](#agreement)
  - [Direction](#direction)
  - [SubDirection](#subdirection)
  - [Service](#service)
  - [Designation](#designation)
  - [Attendance](#attendance)
  - [Education](#education)
  - [Document](#document)
  - [Child](#child)
- [Glossaire des Types de Données](#glossaire-des-types-de-données)

---

## Introduction

L'application **PayDay** est une solution complète de gestion des ressources humaines et de la paie, construite avec Django. Elle permet de gérer les informations des employés, les congés, les avances sur salaire, les éléments de paie, ainsi que les structures organisationnelles. Les modèles de données sont conçus pour être flexibles et répondre aux besoins complexes des entreprises, tout en assurant la traçabilité et la sécurité des informations via des champs d'audit comme `created_by` et `updated_by`.

---

## Modèles de Données

### User

**Description**: Le modèle `User` représente un utilisateur du système, qu'il s'agisse d'un employé, d'un administrateur ou d'un autre rôle. Il gère l'authentification et les autorisations.
**Importance**: Ce modèle est central pour la gestion des accès et des permissions dans l'application, permettant de contrôler qui peut effectuer des actions spécifiques.

**Structure hiérarchique**:

```
User
├── groups ([Group])
│   └── permissions ([Permission])
│       └── content_type (-> ContentType)
└── user_permissions ([Permission])
    └── content_type (-> ContentType)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'utilisateur.
- `last_login` (DateTimeField): Date et heure de la dernière connexion.
- `is_superuser` (BooleanField): Indique si l'utilisateur a toutes les permissions sans assignation explicite.
- `is_staff` (BooleanField): Indique si l'utilisateur peut accéder à l'interface d'administration.
- `is_active` (BooleanField): Indique si l'utilisateur est actif (décocher pour désactiver sans supprimer).
- `date_joined` (DateTimeField): Date d'inscription de l'utilisateur.
- `email` (EmailField): Adresse e-mail de l'utilisateur.
- `password` (CharField): Mot de passe haché de l'utilisateur.
- `created_at` (DateTimeField): Date et heure de création.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `sub_organization` (ChoiceField): Sous-organisation à laquelle l'utilisateur est rattaché.
- `groups` ([Group]): Groupes auxquels l'utilisateur appartient, définissant ses permissions.
- `user_permissions` ([Permission]): Permissions spécifiques attribuées directement à l'utilisateur.

### Group

**Description**: Le modèle `Group` permet de catégoriser les utilisateurs pour leur attribuer des permissions ou des rôles spécifiques.
**Importance**: Il simplifie la gestion des permissions en regroupant les utilisateurs ayant des rôles similaires, comme "Éditeurs de site" ou "Utilisateurs spéciaux".

**Structure hiérarchique**:

```
Group
└── permissions ([Permission])
    └── content_type (-> ContentType)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du groupe.
- `name` (CharField): Nom du groupe.
- `permissions` ([Permission]): Liste des permissions associées au groupe.

### Permission

**Description**: Le modèle `Permission` définit les autorisations spécifiques (ajouter, modifier, supprimer, voir) pour des objets dans l'application.
**Importance**: Il garantit un contrôle d'accès granulaire, essentiel pour la sécurité et la conformité.

**Structure hiérarchique**:

```
Permission
└── content_type (-> ContentType)
```

**Champs**:

- `id` (AutoField): Identifiant unique de la permission.
- `name` (CharField): Nom de la permission.
- `content_type` (-> ContentType): Type de contenu auquel la permission s'applique.
- `codename` (CharField): Nom de code unique pour la permission.

### ContentType

**Description**: Le modèle `ContentType` identifie les modèles de l'application pour associer des permissions spécifiques.
**Importance**: Il permet de lier des permissions à des modèles spécifiques, assurant une gestion dynamique des autorisations.

**Structure hiérarchique**:

```
ContentType
```

**Champs**:

- `id` (AutoField): Identifiant unique du type de contenu.
- `app_label` (CharField): Nom de l'application Django.
- `model` (CharField): Nom de la classe Python du modèle.

### Employee

**Description**: Le modèle `Employee` stocke les informations détaillées des employés, y compris leurs données personnelles, contractuelles et organisationnelles.
**Importance**: Il est au cœur de la gestion des ressources humaines, servant de base pour les congés, la paie et la gestion des présences.

**Structure hiérarchique**:

```
Employee
├── updated_by (-> User)
├── created_by (-> User)
├── agreement (-> Agreement)
├── designation (-> Designation)
├── grade (-> Grade)
├── subdirection (-> SubDirection)
│   └── direction (-> Direction)
├── direction (-> Direction)
├── service (-> Service)
├── branch (-> Branch)
├── status (-> Status)
├── user (-> User)
└── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'employé.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation de l'employé.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `social_security_number` (CharField): Numéro de sécurité sociale.
- `agreement` (-> Agreement): Type de contrat de l'employé.
- `date_of_join` (DateField): Date d'embauche (format YYYY-MM-DD).
- `date_of_end` (DateField): Date de fin de contrat (format YYYY-MM-DD).
- `designation` (-> Designation): Poste occupé.
- `grade` (-> Grade): Niveau hiérarchique.
- `subdirection` (-> SubDirection): Sous-direction de l'employé.
- `direction` (-> Direction): Direction de l'employé.
- `service` (-> Service): Service auquel l'employé est rattaché.
- `middle_name` (CharField): Post-nom de l'employé.
- `first_name` (CharField): Prénom de l'employé.
- `last_name` (CharField): Nom de famille de l'employé.
- `date_of_birth` (DateField): Date de naissance (format YYYY-MM-DD).
- `gender` (CharField): Genre de l'employé.
- `spouse_date_of_birth` (DateField): Date de naissance du conjoint (format YYYY-MM-DD).
- `spouse` (CharField): Nom du conjoint.
- `marital_status` (CharField): État civil.
- `mobile_number` (PhoneNumberField): Numéro de téléphone mobile (format +243 XXX XXX XXX).
- `physical_address` (TextField): Adresse physique.
- `emergency_information` (TextField): Informations de contact en cas d'urgence.
- `branch` (-> Branch): Site où l'employé travaille.
- `payment_account` (CharField): Numéro de compte bancaire.
- `payment_method` (CharField): Mode de paiement (ex. virement, chèque).
- `payer_name` (CharField): Nom du payeur.
- `comment` (TextField): Commentaires supplémentaires.
- `status` (-> Status): Statut de l'employé (ex. actif, inactif).
- `create_user_on_save` (BooleanField): Crée un compte utilisateur si une adresse e-mail est fournie.
- `user` (-> User): Compte utilisateur associé.
- `photo` (ImageField): Photo d'identité (max 1MB).
- `registration_number` (CharField): Matricule unique.
- `email` (EmailField): Adresse e-mail de l'employé.
- `devices` ([Device]): Terminaux de pointage utilisés par l'employé.

### TypeOfLeave

**Description**: Le modèle `TypeOfLeave` définit les différents types de congés disponibles (ex. congé annuel, congé maladie).
**Importance**: Il permet de standardiser et de gérer les politiques de congés, en définissant des règles comme la durée minimale/maximale et l'éligibilité.

**Structure hiérarchique**:

```
TypeOfLeave
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du type de congé.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `name` (CharField): Nom du type de congé.
- `description` (TextField): Description du type de congé.
- `min_duration` (PositiveIntegerField): Durée minimale du congé en jours.
- `max_duration` (PositiveIntegerField): Durée maximale du congé en jours.
- `eligibility_after_days` (PositiveIntegerField): Nombre de jours avant éligibilité.

### EarlyLeave

**Description**: Le modèle `EarlyLeave` enregistre les demandes de départ anticipé des employés pour une journée donnée.
**Importance**: Il permet de suivre les absences partielles, facilitant la gestion des horaires et des présences.

**Structure hiérarchique**:

```
EarlyLeave
├── updated_by (-> User)
├── created_by (-> User)
├── employee (-> Employee)
│   ├── updated_by (-> User)
│   ├── created_by (-> User)
│   ├── agreement (-> Agreement)
│   ├── designation (-> Designation)
│   ├── grade (-> Grade)
│   ├── subdirection (-> SubDirection)
│   │   └── direction (-> Direction)
│   ├── direction (-> Direction)
│   ├── service (-> Service)
│   ├── branch (-> Branch)
│   ├── status (-> Status)
│   ├── user (-> User)
│   └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du départ anticipé.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `employee` (-> Employee): Employé concerné.
- `date` (DateField): Date du départ anticipé.
- `start_time` (TimeField): Heure de début du départ.
- `end_time` (TimeField): Heure de fin du départ.
- `reason` (TextField): Motif du départ anticipé.
- `status` (CharField): Statut de la demande (ex. en attente, approuvé).

### Leave

**Description**: Le modèle `Leave` gère les demandes de congés complets des employés.
**Importance**: Il centralise la gestion des congés, permettant de suivre les absences prolongées et leurs impacts sur la paie.

**Structure hiérarchique**:

```
Leave
├── updated_by (-> User)
├── created_by (-> User)
├── employee (-> Employee)
│   ├── updated_by (-> User)
│   ├── created_by (-> User)
│   ├── agreement (-> Agreement)
│   ├── designation (-> Designation)
│   ├── grade (-> Grade)
│   ├── subdirection (-> SubDirection)
│   │   └── direction (-> Direction)
│   ├── direction (-> Direction)
│   ├── service (-> Service)
│   ├── branch (-> Branch)
│   ├── status (-> Status)
│   ├── user (-> User)
│   └── devices ([Device])
└── type_of_leave (-> TypeOfLeave)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du congé.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `employee` (-> Employee): Employé concerné.
- `type_of_leave` (-> TypeOfLeave): Type de congé demandé.
- `reason` (TextField): Motif du congé.
- `start_date` (DateField): Date de début du congé.
- `end_date` (DateField): Date de fin du congé.
- `status` (CharField): Statut de la demande (ex. en attente, approuvé).

### LegalItem

**Description**: Le modèle `LegalItem` définit les retenues légales (ex. impôts, cotisations sociales) appliquées à la paie.
**Importance**: Il garantit la conformité aux réglementations fiscales et sociales en automatisant les calculs des retenues.

**Structure hiérarchique**:

```
LegalItem
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'élément légal.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `code` (CharField): Code unique de l'élément.
- `type_of_item` (IntegerField): Type d'élément légal.
- `name` (CharField): Nom de l'élément.
- `formula_qp_employer` (AceField): Formule pour la part employeur (Ctrl+Space pour autocomplétion, Ctrl+M pour mode modal).
- `formula_qp_employee` (AceField): Formule pour la part employé (Ctrl+Space pour autocomplétion, Ctrl+M pour mode modal).
- `condition` (AceField): Condition d'application (Ctrl+Space pour autocomplétion, Ctrl+M pour mode modal).
- `is_actif` (BooleanField): Indique si l'élément est actif.

### Item

**Description**: Le modèle `Item` représente les éléments de paie (ex. salaire de base, primes) appliqués aux employés.
**Importance**: Il permet de structurer les composants de la paie, en définissant des formules et des conditions pour les calculs.

**Structure hiérarchique**:

```
Item
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'élément.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `type_of_item` (IntegerField): Type d'élément de paie.
- `code` (CharField): Code unique de l'élément.
- `name` (CharField): Nom de l'élément.
- `formula_qp_employer` (AceField): Formule pour la part employeur.
- `formula_qp_employee` (AceField): Formule pour la part employé.
- `condition` (AceField): Condition d'application.
- `time` (AceField): Temps associé (ex. heures travaillées).
- `is_social_security` (BooleanField): Indique si l'élément est soumis à la sécurité sociale.
- `is_taxable` (BooleanField): Indique si l'élément est imposable.
- `is_bonus` (BooleanField): Indique si l'élément est une prime.
- `is_payable` (BooleanField): Indique si l'élément est payable.
- `is_actif` (BooleanField): Indique si l'élément est actif.

### SpecialEmployeeItem

**Description**: Le modèle `SpecialEmployeeItem` gère les éléments de paie spécifiques attribués à un employé particulier.
**Importance**: Il permet de personnaliser les éléments de paie pour des cas spécifiques, comme des primes exceptionnelles.

**Structure hiérarchique**:

```
SpecialEmployeeItem
├── updated_by (-> User)
├── created_by (-> User)
├── employee (-> Employee)
│   ├── updated_by (-> User)
│   ├── created_by (-> User)
│   ├── agreement (-> Agreement)
│   ├── designation (-> Designation)
│   ├── grade (-> Grade)
│   ├── subdirection (-> SubDirection)
│   │   └── direction (-> Direction)
│   ├── direction (-> Direction)
│   ├── service (-> Service)
│   ├── branch (-> Branch)
│   ├── status (-> Status)
│   ├── user (-> User)
│   └── devices ([Device])
└── item (-> Item)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'élément spécial.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `employee` (-> Employee): Employé concerné.
- `item` (-> Item): Élément de paie associé.
- `amount_qp_employee` (FloatField): Montant pour la part employé (vide pour utiliser la formule).
- `amount_qp_employer` (FloatField): Montant pour la part employeur (vide pour utiliser la formule).
- `end_date` (DateField): Date de fin de validité (vide pour illimité).

### Payroll

**Description**: Le modèle `Payroll` représente une période de paie pour un groupe d'employés.
**Importance**: Il centralise la gestion des salaires, des déductions et des approbations pour une période donnée.

**Structure hiérarchique**:

```
Payroll
├── updated_by (-> User)
├── created_by (-> User)
├── employee_direction ([Direction])
├── employee_status ([Status])
├── employee_branch ([Branch])
├── employee_grade ([Grade])
└── approvers ([User])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de la paie.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `additional_items` (FileField): Fichiers d'éléments additionnels.
- `canvas` (FileField): Canevas de paie.
- `name` (CharField): Nom de la période de paie.
- `start_dt` (DateField): Date de début de la période.
- `end_dt` (DateField): Date de fin de la période.
- `status` (CharField): Statut de la paie (ex. en cours, approuvé).
- `overall_net` (FloatField): Montant net total.
- `approved` (BooleanField): Indique si la paie est approuvée.
- `employee_direction` ([Direction]): Directions incluses (vide pour toutes).
- `employee_status` ([Status]): Statuts inclus (vide pour tous).
- `employee_branch` ([Branch]): Sites inclus (vide pour tous).
- `employee_grade` ([Grade]): Grades inclus (vide pour tous).
- `approvers` ([User]): Utilisateurs autorisés à approuver la paie.

### ItemPaid

**Description**: Le modèle `ItemPaid` enregistre les éléments de paie effectivement payés à un employé.
**Importance**: Il permet de suivre les paiements réels et leurs caractéristiques (ex. imposable, prime).

**Structure hiérarchique**:

```
ItemPaid
├── updated_by (-> User)
├── created_by (-> User)
├── employee (-> PaidEmployee)
│   ├── updated_by (-> User)
│   ├── created_by (-> User)
│   ├── payroll (-> Payroll)
│   │   ├── employee_direction ([Direction])
│   │   ├── employee_status ([Status])
│   │   ├── employee_branch ([Branch])
│   │   ├── employee_grade ([Grade])
│   │   └── approvers ([User])
│   ├── employee (-> Employee)
│   ├── agreement (-> Agreement)
│   ├── designation (-> Designation)
│   ├── grade (-> Grade)
│   ├── subdirection (-> SubDirection)
│   │   └── direction (-> Direction)
│   ├── direction (-> Direction)
│   ├── service (-> Service)
│   ├── branch (-> Branch)
│   ├── status (-> Status)
│   ├── user (-> User)
│   └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'élément payé.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `type_of_item` (IntegerField): Type d'élément payé.
- `code` (CharField): Code de l'élément.
- `name` (CharField): Nom de l'élément.
- `time` (FloatField): Temps associé (ex. heures travaillées).
- `rate` (FloatField): Taux appliqué.
- `amount_qp_employer` (FloatField): Montant payé par l'employeur.
- `amount_qp_employee` (FloatField): Montant payé pour l'employé.
- `employee` (-> PaidEmployee): Fiche de paie de l'employé.
- `social_security_amount` (FloatField): Montant soumis à la sécurité sociale.
- `taxable_amount` (FloatField): Montant imposable.
- `is_payable` (BooleanField): Indique si l'élément est payable.
- `is_bonus` (BooleanField): Indique si l'élément est une prime.

### AdvanceSalary

**Description**: Le modèle `AdvanceSalary` gère les demandes d'avances sur salaire des employés.
**Importance**: Il permet de suivre les avances accordées et leur remboursement, impactant la paie.

**Structure hiérarchique**:

```
AdvanceSalary
├── updated_by (-> User)
├── created_by (-> User)
└── employee (-> Employee)
    ├── updated_by (-> User)
    ├── created_by (-> User)
    ├── agreement (-> Agreement)
    ├── designation (-> Designation)
    ├── grade (-> Grade)
    ├── subdirection (-> SubDirection)
    │   └── direction (-> Direction)
    ├── direction (-> Direction)
    ├── service (-> Service)
    ├── branch (-> Branch)
    ├── status (-> Status)
    ├── user (-> User)
    └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'avance.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `employee` (-> Employee): Employé concerné.
- `status` (CharField): Statut de la demande (ex. en attente, approuvé).
- `duration` (IntegerField): Durée de remboursement en mois.
- `amount` (FloatField): Montant de l'avance.
- `date` (DateField): Date de la demande.

### AdvanceSalaryPayment

**Description**: Le modèle `AdvanceSalaryPayment` enregistre les paiements effectués pour rembourser une avance sur salaire.
**Importance**: Il permet de suivre les remboursements progressifs des avances accordées.

**Structure hiérarchique**:

```
AdvanceSalaryPayment
├── updated_by (-> User)
├── created_by (-> User)
└── advance_salary (-> AdvanceSalary)
    └── employee (-> Employee)
        ├── updated_by (-> User)
        ├── created_by (-> User)
        ├── agreement (-> Agreement)
        ├── designation (-> Designation)
        ├── grade (-> Grade)
        ├── subdirection (-> SubDirection)
        │   └── direction (-> Direction)
        ├── direction (-> Direction)
        ├── service (-> Service)
        ├── branch (-> Branch)
        ├── status (-> Status)
        ├── user (-> User)
        └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du paiement.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `advance_salary` (-> AdvanceSalary): Avance sur salaire associée.
- `date` (DateField): Date du paiement.
- `amount` (FloatField): Montant du paiement.

### PaidEmployee

**Description**: Le modèle `PaidEmployee` représente les informations d'un employé pour une période de paie spécifique.
**Importance**: Il centralise les données de paie, incluant les montants bruts, nets et les retenues.

**Structure hiérarchique**:

```
PaidEmployee
├── updated_by (-> User)
├── created_by (-> User)
├── payroll (-> Payroll)
│   ├── employee_direction ([Direction])
│   ├── employee_status ([Status])
│   ├── employee_branch ([Branch])
│   ├── employee_grade ([Grade])
│   └── approvers ([User])
├── employee (-> Employee)
├── agreement (-> Agreement)
├── designation (-> Designation)
├── grade (-> Grade)
├── subdirection (-> SubDirection)
│   └── direction (-> Direction)
├── direction (-> Direction)
├── service (-> Service)
├── branch (-> Branch)
├── status (-> Status)
├── user (-> User)
└── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de la fiche de paie.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `social_security_number` (CharField): Numéro de sécurité sociale.
- `date_of_join` (DateField): Date d'embauche.
- `date_of_end` (DateField): Date de fin de contrat.
- `middle_name` (CharField): Post-nom.
- `first_name` (CharField): Prénom.
- `last_name` (CharField): Nom de famille.
- `date_of_birth` (DateField): Date de naissance.
- `gender` (CharField): Genre.
- `spouse_date_of_birth` (DateField): Date de naissance du conjoint.
- `spouse` (CharField): Nom du conjoint.
- `marital_status` (CharField): État civil.
- `mobile_number` (PhoneNumberField): Numéro de téléphone mobile.
- `physical_address` (TextField): Adresse physique.
- `emergency_information` (TextField): Informations d'urgence.
- `payment_account` (CharField): Numéro de compte bancaire.
- `payment_method` (CharField): Mode de paiement.
- `payer_name` (CharField): Nom du payeur.
- `comment` (TextField): Commentaires.
- `payroll` (-> Payroll): Période de paie associée.
- `employee` (-> Employee): Employé concerné.
- `attendance` (IntegerField): Jours de présence.
- `registration_number` (CharField): Matricule.
- `agreement` (CharField): Type de contrat.
- `status` (CharField): Statut de l'employé.
- `designation` (CharField): Poste occupé.
- `branch` (CharField): Site.
- `grade` (CharField): Niveau hiérarchique.
- `subdirection` (CharField): Sous-direction.
- `direction` (CharField): Direction.
- `service` (CharField): Service.
- `working_days_per_month` (IntegerField): Jours ouvrables par mois.
- `children` (IntegerField): Nombre d'enfants.
- `social_security_threshold` (FloatField): Plafond de sécurité sociale.
- `taxable_gross` (FloatField): Montant brut imposable.
- `gross` (FloatField): Montant brut total.
- `net` (FloatField): Montant net payé.

### Grade

**Description**: Le modèle `Grade` définit les niveaux hiérarchiques au sein de l'organisation.
**Importance**: Il permet de structurer les employés selon leur niveau de responsabilité et leur rémunération.

**Structure hiérarchique**:

```
Grade
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du grade.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `group` (CharField): Groupe associé au grade.
- `name` (CharField): Nom du grade.

### Status

**Description**: Le modèle `Status` définit les statuts possibles des employés (ex. actif, en congé, retraité).
**Importance**: Il permet de suivre l'état actuel des employés pour la gestion des ressources humaines et de la paie.

**Structure hiérarchique**:

```
Status
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du statut.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `group` (CharField): Groupe associé au statut.
- `name` (CharField): Nom du statut.

### Branch

**Description**: Le modèle `Branch` représente les différents sites physiques de l'organisation.
**Importance**: Il permet de localiser les employés et de gérer les ressources par site.

**Structure hiérarchique**:

```
Branch
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du site.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `group` (CharField): Groupe associé au site.
- `name` (CharField): Nom du site.

### Agreement

**Description**: Le modèle `Agreement` définit les types de contrats des employés (ex. CDI, CDD).
**Importance**: Il structure les conditions contractuelles, influençant les droits et les obligations des employés.

**Structure hiérarchique**:

```
Agreement
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du contrat.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `group` (CharField): Groupe associé au contrat.
- `name` (CharField): Nom du contrat.

### Direction

**Description**: Le modèle `Direction` représente les grandes divisions organisationnelles (ex. direction financière).
**Importance**: Il organise les employés selon les grandes unités stratégiques de l'entreprise.

**Structure hiérarchique**:

```
Direction
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de la direction.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `name` (CharField): Nom de la direction.

### SubDirection

**Description**: Le modèle `SubDirection` représente les sous-divisions au sein d'une direction.
**Importance**: Il permet une organisation plus fine des employés au sein des directions.

**Structure hiérarchique**:

```
SubDirection
├── updated_by (-> User)
├── created_by (-> User)
└── direction (-> Direction)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de la sous-direction.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `direction` (-> Direction): Direction à laquelle la sous-direction est rattachée.
- `name` (CharField): Nom de la sous-direction.

### Service

**Description**: Le modèle `Service` définit les unités opérationnelles au sein d'une sous-direction.
**Importance**: Il permet de structurer les employés selon leurs fonctions opérationnelles spécifiques.

**Structure hiérarchique**:

```
Service
├── updated_by (-> User)
├── created_by (-> User)
└── subdirection (-> SubDirection)
    └── direction (-> Direction)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du service.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `subdirection` (-> SubDirection): Sous-direction à laquelle le service est rattaché.
- `name` (CharField): Nom du service.

### Designation

**Description**: Le modèle `Designation` définit les postes ou rôles spécifiques des employés.
**Importance**: Il permet de catégoriser les employés selon leurs responsabilités professionnelles.

**Structure hiérarchique**:

```
Designation
├── updated_by (-> User)
└── created_by (-> User)
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du poste.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `group` (CharField): Groupe associé au poste.
- `working_days_per_month` (IntegerField): Nombre de jours ouvrables par mois.
- `name` (CharField): Nom du poste.

### Attendance

**Description**: Le modèle `Attendance` enregistre les données de présence des employés via des terminaux de pointage.
**Importance**: Il permet de suivre la présence pour calculer la paie et gérer les absences.

**Structure hiérarchique**:

```
Attendance
├── updated_by (-> User)
├── created_by (-> User)
├── device (-> Device)
└── employee (-> Employee)
    ├── updated_by (-> User)
    ├── created_by (-> User)
    ├── agreement (-> Agreement)
    ├── designation (-> Designation)
    ├── grade (-> Grade)
    ├── subdirection (-> SubDirection)
    │   └── direction (-> Direction)
    ├── direction (-> Direction)
    ├── service (-> Service)
    ├── branch (-> Branch)
    ├── status (-> Status)
    ├── user (-> User)
    └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'enregistrement de présence.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `device` (-> Device): Terminal de pointage utilisé.
- `employee` (-> Employee): Employé concerné.
- `first_checked_at` (DateTimeField): Heure de pointage d'entrée.
- `last_checked_at` (DateTimeField): Heure de pointage de sortie.
- `checked_at` (DateTimeField): Heure de vérification.
- `count` (IntegerField): Nombre de présences enregistrées.

### Education

**Description**: Le modèle `Education` enregistre les informations sur la formation académique des employés.
**Importance**: Il permet de documenter les qualifications des employés pour des décisions RH.

**Structure hiérarchique**:

```
Education
├── updated_by (-> User)
├── created_by (-> User)
└── employee (-> Employee)
    ├── updated_by (-> User)
    ├── created_by (-> User)
    ├── agreement (-> Agreement)
    ├── designation (-> Designation)
    ├── grade (-> Grade)
    ├── subdirection (-> SubDirection)
    │   └── direction (-> Direction)
    ├── direction (-> Direction)
    ├── service (-> Service)
    ├── branch (-> Branch)
    ├── status (-> Status)
    ├── user (-> User)
    └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'enregistrement de formation.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `employee` (-> Employee): Employé concerné.
- `institution` (CharField): Nom de l'institution.
- `degree` (CharField): Diplôme obtenu.
- `start_date` (DateField): Date de début de la formation.
- `end_date` (DateField): Date de fin de la formation.

### Document

**Description**: Le modèle `Document` stocke les documents associés aux employés (ex. contrats, certificats).
**Importance**: Il permet de centraliser et de gérer les documents administratifs des employés.

**Structure hiérarchique**:

```
Document
├── updated_by (-> User)
├── created_by (-> User)
└── employee (-> Employee)
    ├── updated_by (-> User)
    ├── created_by (-> User)
    ├── agreement (-> Agreement)
    ├── designation (-> Designation)
    ├── grade (-> Grade)
    ├── subdirection (-> SubDirection)
    │   └── direction (-> Direction)
    ├── direction (-> Direction)
    ├── service (-> Service)
    ├── branch (-> Branch)
    ├── status (-> Status)
    ├── user (-> User)
    └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique du document.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `employee` (-> Employee): Employé concerné.
- `document` (FileField): Fichier du document.
- `name` (CharField): Nom du document.

### Child

**Description**: Le modèle `Child` enregistre les informations sur les enfants des employés.
**Importance**: Il permet de gérer les données familiales pour des avantages sociaux ou des calculs de paie.

**Structure hiérarchique**:

```
Child
├── updated_by (-> User)
├── created_by (-> User)
└── employee (-> Employee)
    ├── updated_by (-> User)
    ├── created_by (-> User)
    ├── agreement (-> Agreement)
    ├── designation (-> Designation)
    ├── grade (-> Grade)
    ├── subdirection (-> SubDirection)
    │   └── direction (-> Direction)
    ├── direction (-> Direction)
    ├── service (-> Service)
    ├── branch (-> Branch)
    ├── status (-> Status)
    ├── user (-> User)
    └── devices ([Device])
```

**Champs**:

- `id` (BigAutoField): Identifiant unique de l'enfant.
- `_metadata` (JSONField): Métadonnées supplémentaires.
- `sub_organization` (ChoiceField): Sous-organisation associée.
- `updated_by` (-> User): Utilisateur ayant mis à jour l'enregistrement.
- `created_by` (-> User): Utilisateur ayant créé l'enregistrement.
- `updated_at` (DateTimeField): Date et heure de la dernière mise à jour.
- `created_at` (DateTimeField): Date et heure de création.
- `employee` (-> Employee): Employé parent.
- `full_name` (CharField): Nom complet de l'enfant.
- `date_of_birth` (DateField): Date de naissance de l'enfant.

---

## Glossaire des Types de Données

- **BigAutoField**: Identifiant unique auto-incrémenté (entier 64 bits).
- **JSONField**: Champ pour stocker des données au format JSON.
- **ChoiceField**: Champ avec une liste de choix prédéfinis.
- **DateTimeField**: Champ pour stocker une date et une heure (ex. 2025-07-09 14:30:00).
- **BooleanField**: Champ booléen (vrai ou faux).
- **EmailField**: Champ pour stocker une adresse e-mail valide.
- **CharField**: Champ pour stocker une chaîne de caractères (longueur limitée).
- **TextField**: Champ pour stocker du texte long.
- **PositiveIntegerField**: Champ pour stocker un entier positif.
- **DateField**: Champ pour stocker une date (format YYYY-MM-DD).
- **PhoneNumberField**: Champ pour stocker un numéro de téléphone (ex. +243 XXX XXX XXX).
- **ImageField**: Champ pour stocker une image (max 1MB pour `photo`).
- **FileField**: Champ pour stocker un fichier.
- **IntegerField**: Champ pour stocker un entier.
- **FloatField**: Champ pour stocker un nombre à virgule flottante.
- **AceField**: Champ pour stocker des formules ou du code avec autocomplétion (Ctrl+Space) et mode modal (Ctrl+M).
- **ForeignKey (-> Model)**: Relation vers un autre modèle (clé étrangère).
- **ManyToManyField ([Model])**: Relation multiple vers un autre modèle.
