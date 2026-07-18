# Table structure

## 0_ПЛАН
Planning layer: date, routine, object, object ID, shooting goal, notes, plan status, owner.

## 1_РЕЕСТР_СЪЕМОК
Fact layer: object ID, shooting date, hotel, operator, source material status, Drive link, operator notes.

## 2_ТРЕКЕР_ПРОДАКШНА
Production layer: added date, hotel, operator/sorter, material type, shooting date, production status, Drive link, comments, site URL.

## 3_АУДИТ_САЙТА
Audit layer: issue date, link, hotel, defect type, problem description, reporter, status, object ID, urgency, transfer status.

## 99_СПРАВОЧНИКИ
Reference layer: hotels, team, plan statuses, material types, production statuses, source statuses, IDs, URLs, priorities.
