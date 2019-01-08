
// sse alerts
function flashhandler(event) {
	html = "<div class='alert alert-" + event.type +
		" alert-dismissible' role='alert' data-dismiss='alert' data-toggle='tooltip' title='Click to close'>" +
		event.data + "</div>";
	$(html).prependTo('#flash');
}

function messagehandler(event) {
	 var obj = JSON.parse(event.data);
	html = "<div class='alert alert-" + obj.level +
		" alert-dismissible' role='alert' data-dismiss='alert' data-toggle='tooltip' title='Click to close'>" +
		obj.message + "</div>";
	$(html).prependTo('#flash');
}

function tickerhandler(event) {
	data = JSON.parse(event.data);

	pticker = '#panel-ticker-' + data.ticker.pair;
	ptprice = pticker + " .panel-ticker-price";
	ptoc    = pticker + " .panel-ticker-oc";
	oldprice = $(ptprice).text();
	if (oldprice < data.ticker.price) {
		hgstyle = {"background-color": "darkGreen"};
		bgcol = "darkGreen";
	} else {
		hgstyle = {"background-color": "darkRed"};
		bgcol = "darkRed";
	}
	nstyle = {"background-color": "#2f485a"};
	$(pticker).css("background-color", bgcol);
	$(pticker).fadeOut("slow");
	$(ptprice).text(data.ticker.price);
	$(pticker + " .panel-ticker-oc").text(Number((data.m1440.oc).toFixed(2)) + "%"); 
	if ( data.m1440.oc >= 0){
		$(ptoc).css("color", "lawnGreen");
	} else {
		$(ptoc).css("color", "red");
	}
	$(pticker).fadeIn("fast")
	setTimeout(function() { $(pticker).css(nstyle) ; }, 2000);
}

$(window).on('beforeunload', function(){
   		flashsse.close();
		tickersse.close();
		vircpubsse.close();
});

// Confirm with 'confirmation' class
$('.confirmation').on('click', function () {
	return confirm('Are you sure?');
});
