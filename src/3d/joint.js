define(function(require) {

    var Node = require("./node");
    var Quaternion = require("core/quaternion");
    var Vector3 = require("core/vector3");
    var Matrix4 = require("core/matrix4");
    
    var Joint = Node.derive(function() {
        return {
            // Index of bone
            index : -1,
            // Parent bone index
            parentIndex : -1,
            //{
            //  time : 
            //  position : 
            //  rotation :
            //  scale :
            //}
            poses : [],

            _cacheKey : 0
        }
    }, {

        setPose : function(time) {

            this._interpolateField(time, 'position');
            this._interpolateField(time, 'rotation');
            this._interpolateField(time, 'scale');

        },

        _interpolateField : function(time, fieldName) {
            var poses = this.poses;
            var len = poses.length;
            var start;
            var end;

            for (var i = this._cacheKey; i < len; i++) {
                if (poses[i].time <= time && poses[i][fieldName]) {
                    start = poses[i];
                    this._cacheKey = i;
                } else if (poses[i][fieldName]) {
                    end = poses[i];
                    break;
                }
            }

            if (start && end) {
                var percent = (time-start.time) / (end.time-start.time);
                percent = Math.max(Math.min(percent, 1), 0);
                if (fieldName === "rotation") {
                    this[fieldName].slerp(start[fieldName], end[fieldName], percent);
                } else {
                    this[fieldName].lerp(start[fieldName], end[fieldName], percent);
                }
            } else {
                this._cacheKey = 0;
            }
        }
    });

    return Joint;
})