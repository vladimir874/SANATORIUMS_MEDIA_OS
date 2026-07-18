{
    app.beginUndoGroup("Sanatoriums Auto-Template");

    // 1. Создаем композицию
    var compName = "Sanatoriums_Info_List";
    var comp = app.project.items.addComp(compName, 1920, 1080, 1.0, 10, 25);
    comp.openInViewer();

    // 2. Создаем текст
    var textString = "1. Нет приема врача\r2. Только физиотерапевт\r3. Без домашних животных\r4. Ограниченный вид на море";
    var textLayer = comp.layers.addText(textString);
    textLayer.name = "Text_List";
    
    // Используем строгие MatchNames для свойств
    var textProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
    var textDoc = textProp.value;
    textDoc.fontSize = 45;
    textDoc.fillColor = [43/255, 43/255, 43/255]; 
    textDoc.justification = ParagraphJustification.LEFT_JUSTIFY;
    textDoc.font = "Arial-BoldMT"; 
    textProp.setValue(textDoc);

    // 3. Создаем Shape Layer (плашку)
    var shapeLayer = comp.layers.addShape();
    shapeLayer.name = "Dynamic_Box";
    shapeLayer.moveAfter(textLayer);
    shapeLayer.property("ADBE Transform Group").property("ADBE Position").setValue([0, 0]); 

    var shapeContents = shapeLayer.property("ADBE Root Vectors Group");

    // --- БЕЛАЯ ПЛАШКА ---
    var whiteGroup = shapeContents.addProperty("ADBE Vector Group");
    whiteGroup.name = "White_Box";
    var whiteGroupContents = whiteGroup.property("ADBE Vectors Group");
    
    var rect = whiteGroupContents.addProperty("ADBE Vector Shape - Rect");
    // Экспрешены привязаны ТОЛЬКО к тексту (sourceRectAtTime работает на всех языках)
    rect.property("ADBE Vector Rect Size").expression = "var txt = thisComp.layer('Text_List').sourceRectAtTime();\r[txt.width + 90, txt.height + 70];";
    rect.property("ADBE Vector Rect Position").expression = "var txt = thisComp.layer('Text_List').sourceRectAtTime();\r[txt.left + txt.width/2 - 5, txt.top + txt.height/2];";
    
    var fill = whiteGroupContents.addProperty("ADBE Vector Graphic - Fill");
    fill.property("ADBE Vector Fill Color").setValue([1, 1, 1]); 

    // --- ЗЕЛЕНАЯ ЛИНИЯ ---
    var greenGroup = shapeContents.addProperty("ADBE Vector Group");
    greenGroup.name = "Green_Line";
    var greenGroupContents = greenGroup.property("ADBE Vectors Group");
    
    var lineRect = greenGroupContents.addProperty("ADBE Vector Shape - Rect");
    // Абсолютно независимая формула координат (отвязанная от белой плашки)
    lineRect.property("ADBE Vector Rect Size").expression = "var txt = thisComp.layer('Text_List').sourceRectAtTime();\r[12, txt.height + 70];";
    lineRect.property("ADBE Vector Rect Position").expression = "var txt = thisComp.layer('Text_List').sourceRectAtTime();\r[txt.left - 44, txt.top + txt.height/2];";
    
    var lineFill = greenGroupContents.addProperty("ADBE Vector Graphic - Fill");
    lineFill.property("ADBE Vector Fill Color").setValue([72/255, 192/255, 20/255]); 

    // --- ТЕНЬ (в безопасном блоке) ---
    try {
        var dropShadow = shapeLayer.property("ADBE Effect Parade").addProperty("ADBE Drop Shadow");
        dropShadow.property("ADBE Drop Shadow-0002").setValue(15); // Opacity
        dropShadow.property("ADBE Drop Shadow-0004").setValue(10); // Distance
        dropShadow.property("ADBE Drop Shadow-0005").setValue(40); // Softness
    } catch(e) {
        // Если русская версия заблокирует эффект, скрипт не упадет, а просто пойдет дальше
    }

    // 4. Анимация выезда
    var posProp = textLayer.property("ADBE Transform Group").property("ADBE Position");
    posProp.setValueAtTime(0, [2100, 400]);
    posProp.setValueAtTime(1, [1200, 400]);
    
    // Плавность анимации (Easy Ease In)
    posProp.setInterpolationTypeAtKey(1, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    posProp.setInterpolationTypeAtKey(2, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);

    app.endUndoGroup();
}