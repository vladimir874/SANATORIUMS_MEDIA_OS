{
    app.beginUndoGroup("Sanatoriums Auto-Template");

    // 1. Создаем новую композицию 1920x1080
    var compName = "Sanatoriums_Info_List";
    var comp = app.project.items.addComp(compName, 1920, 1080, 1.0, 10, 25);
    comp.openInViewer();

    // 2. Создаем текстовый слой с нашими пунктами
    var textString = "1. Нет приема врача\r2. Только физиотерапевт\r3. Без домашних животных\r4. Ограниченный вид на море";
    var textLayer = comp.layers.addText(textString);
    textLayer.name = "Text_List";
    
    // Настраиваем стиль текста (размер, выравнивание, цвет)
    var textProp = textLayer.property("Source Text");
    var textDoc = textProp.value;
    textDoc.fontSize = 45;
    textDoc.fillColor = [43/255, 43/255, 43/255]; // Темно-серый цвет для читаемости
    textDoc.justification = ParagraphJustification.LEFT_JUSTIFY;
    // Скрипт попытается применить стандартный Arial Bold, 
    // так как системное имя Encode Sans может отличаться на разных ПК.
    // Замени шрифт на Encode Sans Normal bold вручную в панели Character!
    textDoc.font = "Arial-BoldMT"; 
    textProp.setValue(textDoc);

    // 3. Создаем плашку (Shape Layer)
    var shapeLayer = comp.layers.addShape();
    shapeLayer.name = "Dynamic_Box";
    shapeLayer.moveAfter(textLayer);
    shapeLayer.property("Position").setValue([0, 0]); // Оставляем в нулях для правильной работы экспрешенов

    // Добавляем белую основу
    var shapeGroup = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
    shapeGroup.name = "White_Box";
    var rect = shapeGroup.property("Contents").addProperty("ADBE Vector Shape - Rect");
    var fill = shapeGroup.property("Contents").addProperty("ADBE Vector Graphic - Fill");
    fill.property("Color").setValue([1, 1, 1]); // Белый цвет

    // Умные выражения (Expressions) для идеального облегания текста
    rect.property("Size").expression = "var txt = thisComp.layer('Text_List').sourceRectAtTime();\r[txt.width + 90, txt.height + 70];";
    rect.property("Position").expression = "var txt = thisComp.layer('Text_List').sourceRectAtTime();\r[txt.left + txt.width/2 - 5, txt.top + txt.height/2];";

    // Добавляем зеленую линию Sanatoriums (#48C014)
    var lineGroup = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
    lineGroup.name = "Green_Line";
    var lineRect = lineGroup.property("Contents").addProperty("ADBE Vector Shape - Rect");
    var lineFill = lineGroup.property("Contents").addProperty("ADBE Vector Graphic - Fill");
    lineFill.property("Color").setValue([72/255, 192/255, 20/255]); // Тот самый зеленый из гайдлайна

    // Выражения для зеленой линии (всегда слева от белой плашки)
    lineRect.property("Size").expression = "var box = content('White_Box').content('Rectangle Path 1').size;\r[12, box[1]];";
    lineRect.property("Position").expression = "var boxPos = content('White_Box').content('Rectangle Path 1').position;\rvar boxSize = content('White_Box').content('Rectangle Path 1').size;\r[boxPos[0] - boxSize[0]/2 + 6, boxPos[1]];";

    // Добавляем легкую тень для премиальности
    var dropShadow = shapeLayer.property("Effects").addProperty("ADBE Drop Shadow");
    dropShadow.property("Opacity").setValue(15);
    dropShadow.property("Distance").setValue(10);
    dropShadow.property("Softness").setValue(40);

    // 4. Анимация (Текст выезжает, а плашка тянется за ним благодаря коду)
    var posProp = textLayer.property("Position");
    // Ключ 1: за экраном
    posProp.setValueAtTime(0, [2100, 400]);
    // Ключ 2: на месте (справа от ведущего)
    posProp.setValueAtTime(1, [1200, 400]);

    // Делаем анимацию плавной (Easy Ease In)
    posProp.setInterpolationTypeAtKey(1, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    posProp.setInterpolationTypeAtKey(2, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);

    app.endUndoGroup();
}